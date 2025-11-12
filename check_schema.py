from backend.db_tools import get_schema_map, clear_schema_cache
import json
import sys

def main():
    try:
        # Clear the schema cache first
        print("Clearing schema cache...")
        clear_schema_cache()
        
        # Get the schema map
        print("\nGetting fresh schema map...")
        schema_map = get_schema_map()
        
        # Print debug info about the schema map
        print(f"\nType of schema_map: {type(schema_map)}")
        print(f"Schema map keys: {list(schema_map.keys())}")
        print(f"Number of schemas: {len(schema_map)}")
        if len(schema_map) > 0:
            print("First 1-2 schemas:")
            for i, (k, v) in enumerate(schema_map.items()):
                print(f"- {k}: tables={list(v.get('tables', {}).keys())}")
                if i >= 1:
                    break
        else:
            print("Schema map is empty!")
        
        # Print the entire schema map structure
        print("\nFull Schema Map Structure:")
        print(json.dumps(schema_map, indent=2))
        
        # Specifically check Sales.Customers
        print("\nChecking Sales.Customers table:")
        if 'Sales' in schema_map:
            print("Sales schema exists")
            if 'tables' in schema_map['Sales']:
                print("Tables in Sales schema:", list(schema_map['Sales']['tables'].keys()))
                if 'Customers' in schema_map['Sales']['tables']:
                    print("\nCustomers table structure:")
                    print(json.dumps(schema_map['Sales']['tables']['Customers'], indent=2))
                else:
                    print("Customers table not found in Sales schema")
            else:
                print("No tables found in Sales schema")
        else:
            print("Sales schema not found")
    except Exception as e:
        print(f"Exception occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 