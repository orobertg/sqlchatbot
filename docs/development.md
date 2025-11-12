# Development Guidelines

## Code Structure
sqlchatbot/
├── app/
│   ├── streamlit_app.py
│   ├── configuration.py
│   └── chat.py
├── backend/
│   ├── sql_connector.py
│   └── llm_engine.py
├── docs/
│   ├── architecture.md
│   ├── setup.md
│   └── development.md
└── requirements.txt

## Critical Development Rules

### 1. Streamlit Configuration
- st.set_page_config() must only exist in streamlit_app.py
- It must be the first Streamlit command
- Never add it to other files
- Always check for this when making changes

### 2. Session State
- Initialize all state variables in streamlit_app.py
- Use try-except when accessing state in other files
- Document new state variables
- Current state variables:
  * log_messages
  * db_connected
  * llm_connected
  * chat_history

### 3. Logging
- Use the custom StreamlitHandler
- Buffer logs until Streamlit is ready
- Use appropriate log levels
- Check logging initialization order

## Best Practices

### Code Style
- Follow PEP 8
- Use type hints
- Document functions and classes
- Keep functions focused and small
- Use meaningful variable names
- Add comments for complex logic

### Error Handling
- Use try-except blocks
- Log errors appropriately
- Provide user-friendly error messages
- Handle edge cases
- Validate inputs
- Check connection states

### Testing
- Write unit tests
- Test configuration changes
- Verify session state
- Check component interactions
- Test error handling
- Validate user inputs

## Common Issues

### 1. Page Configuration Error
WRONG:
# In any file other than streamlit_app.py
st.set_page_config(...)  # Will cause error

RIGHT:
# Only in streamlit_app.py, as first command
st.set_page_config(...)

### 2. Session State Access
WRONG:
value = st.session_state.undefined_key  # May raise error

RIGHT:
value = st.session_state.get('undefined_key', default_value)

### 3. Component Updates
- Always test after component changes
- Verify session state initialization
- Check logging functionality
- Test error handling
- Validate user experience

## Pull Request Guidelines
1. Update documentation
2. Add tests
3. Follow code style
4. Test all components
5. Update requirements if needed
6. Check for common issues
7. Test on different platforms

## Development Workflow
1. Create feature branch
2. Make changes
3. Run tests
4. Update documentation
5. Create pull request
6. Address review comments
7. Merge after approval

## Debugging Tips
1. Use st.write() for debugging
2. Check session state values
3. Monitor log messages
4. Test component isolation
5. Verify data flow
6. Check environment variables

## Performance Considerations
1. Optimize database queries
2. Monitor memory usage
3. Cache expensive operations
4. Clean up resources
5. Handle large datasets
6. Profile slow operations 