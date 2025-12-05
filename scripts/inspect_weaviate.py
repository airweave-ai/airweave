import weaviate
import json
import os

def inspect_chunks(limit=10):
    print(f"Connecting to Weaviate at http://localhost:8090...")
    
    # Connect to local Weaviate using v4 client
    client = weaviate.connect_to_local(port=8090, grpc_port=50051)
    
    try:
        # Get all collections
        collections = client.collections.list_all()
        print(f"Found collections: {list(collections.keys())}")

        for name, collection in collections.items():
            print(f"\n--- Inspecting Collection: {name} ---")
            
            # Fetch objects
            response = collection.query.fetch_objects(
                limit=limit,
                include_vector=True
            )
            
            objects = response.objects
            print(f"Found {len(objects)} chunks (showing max {limit}):")
            
            for i, obj in enumerate(objects):
                print(f"\n[Chunk {i+1}]")
                print(f"ID: {obj.uuid}")
                print(f"Properties: {json.dumps(obj.properties, indent=2)}")
                if obj.vector:
                     # Handle both list and dict vector formats if applicable, though usually list in v4
                    vector_len = len(obj.vector['default']) if isinstance(obj.vector, dict) else len(obj.vector)
                    print(f"Vector Length: {vector_len}")
                else:
                    print("Vector: Not retrieved")

    finally:
        client.close()

if __name__ == "__main__":
    try:
        inspect_chunks()
    except Exception as e:
        print(f"Error: {e}")
