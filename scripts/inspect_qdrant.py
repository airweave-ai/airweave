from qdrant_client import QdrantClient
import json

def inspect_chunks(limit=10):
    print("Connecting to Qdrant at http://localhost:6333...")
    
    client = QdrantClient(url="http://localhost:6333")
    
    try:
        collections = client.get_collections()
        print(f"Found {len(collections.collections)} collections: {[c.name for c in collections.collections]}")
        
        for collection in collections.collections:
            name = collection.name
            print(f"\n--- Inspecting Collection: {name} ---")
            
            # Scroll through points
            result, _ = client.scroll(
                collection_name=name,
                limit=limit,
                with_payload=True,
                with_vectors=False # Set to True to see vectors
            )
            
            print(f"Found {len(result)} chunks (showing max {limit}):")
            
            for i, point in enumerate(result):
                print(f"\n[Chunk {i+1}]")
                print(f"ID: {point.id}")
                print(f"Payload: {json.dumps(point.payload, indent=2)}")

    except Exception as e:
        print(f"Error inspecting Qdrant: {e}")

if __name__ == "__main__":
    inspect_chunks()
