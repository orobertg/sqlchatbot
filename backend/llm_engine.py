import os
import json
import re
import logging
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import openai
from backend.tools import get_schema_map_from_cache

# Setup
logging.basicConfig(level=logging.INFO)
load_dotenv()

LLM_MODEL_NAME = os.getenv("LLM_MODEL", "llama3.2")
openai.api_base = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/") + "/"
openai.api_key = os.getenv("OPENAI_API_KEY", "ollama")

# --- Pydantic Prompt Models ---

class SQLPrompt(BaseModel):
    description: str = Field(..., description="User input")

    def to_full_prompt(self) -> str:
        schema_map = get_schema_map_from_cache()
        schema_description = json.dumps(schema_map, indent=2)
        return (
            "You are a helpful SQL assistant. Below is the schema map.\n\n"
            "Use ONLY these schemas, tables and respective table column names to write SQL.\n"
            "Respond with ONLY the SQL query.\n"
            "Always include the correct SCHEMA name for tables (e.g., Sales.Orders).\n"
            "Always verify column exists in the table EXACTLY as shown in the schema map.\n"
            "Do not hallucinate a column name that does not exist in the schema map.\n"
            "If a column does not exist in schema map but in your SQL query, respond with: 'Error: Table or column not found.'\n"
            "Carefully cross-check each table and column against the schema map. Do NOT assume column names. Do NOT guess.\n"
            "Do not add commentary or explanation.\n\n"
            f"{schema_description}\n\n"
            f"User Question: {self.description}\n\nSQL:"
        )

class SQLResponse(BaseModel):
    sql_query: str = Field(...)

    @field_validator("sql_query")
    def validate_sql(cls, v):
        if not re.match(r"^(SELECT|INSERT|UPDATE|DELETE|WITH)\b", v, re.IGNORECASE):
            raise ValueError("Output is not valid SQL.")
        return v

# --- Main LLM Wrapper ---

class LocalLLM:
    def __init__(self, model: str, max_tokens: int = 200, temperature: float = 0.2):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = openai.OpenAI(base_url=openai.api_base, api_key=openai.api_key)
        self._verify_model()

    def _verify_model(self):
        try:
            # Safely fix endpoint for model list
            base_url = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3].rstrip("/")
            url = f"{base_url}/api/tags"

            logging.info(f"[LLM] Verifying model using URL: {url}")
            response = requests.get(url)
            response.raise_for_status()

            models = [m["name"] for m in response.json().get("models", [])]
            if self.model not in models:
                raise ValueError(f"Model '{self.model}' not found. Available models: {models}")
            logging.info(f"[LLM] Model '{self.model}' verified.")
        except Exception as e:
            raise RuntimeError(f"[LLM Error] Model verification failed: {e}")

    def generate_sql(self, prompt: SQLPrompt):
        full_prompt = prompt.to_full_prompt()
        messages = [
            {"role": "system", "content": "You are a SQL assistant. Output valid SQL only."},
            {"role": "user", "content": full_prompt}
        ]

        logging.info("🧠 Full Prompt:\n%s", full_prompt)
        logging.info("📨 Messages to LLM:\n%s", json.dumps(messages, indent=2))

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            generated_text = response.choices[0].message.content.strip()
            logging.info("🧾 Raw LLM Output:\n%s", generated_text)

            match = re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b.*', generated_text, re.IGNORECASE | re.DOTALL)
            if not match:
                raise RuntimeError(f"LLM did not return SQL. Raw output:\n{generated_text}")

            sql_query = match.group(0).strip()
            return SQLResponse(sql_query=sql_query), generated_text, full_prompt

        except Exception as e:
            raise RuntimeError(f"Error generating SQL: {e}")

# --- Instance Management ---

LLM_INSTANCE = None

def set_llm_instance(model: str):
    global LLM_INSTANCE
    try:
        LLM_INSTANCE = LocalLLM(model)
        logging.info(f"[LLM] Instance set to model: {model}")
    except Exception as e:
        logging.error(f"[LLM Error] Failed to set instance: {e}")
        LLM_INSTANCE = None
        raise

def get_llm_instance():
    return LLM_INSTANCE

def generate_sql(user_prompt: str):
    if LLM_INSTANCE is None:
        set_llm_instance(LLM_MODEL_NAME)
    try:
        prompt_model = SQLPrompt(description=user_prompt)
        response_model, raw_output, full_prompt = LLM_INSTANCE.generate_sql(prompt_model)
        return response_model.sql_query, raw_output, full_prompt
    except Exception as e:
        return f"-- Error generating SQL: {e}", "", ""
