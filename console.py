#!/usr/bin/env python
"""
Console interface for IngestionEngine
"""

import os
import logging
from ingestion_engine.ingestion_engine import IngestionEngine
from graphrouter import Ontology
from graphrouter.core_ontology import create_core_ontology, extend_ontology

def setup_ontology():
    """Create ontology with proper type definitions"""
    base_ontology = create_core_ontology()

    # Add any additional custom types if needed (for now, an empty extension)
    extensions = Ontology()

    return extend_ontology(base_ontology, extensions)

def print_ontology(engine):
    """Display current ontology"""
    print("\nNode Types:")
    for label, details in engine.ontology.node_types.items():
        print(f"\n{label}:")
        print("  Properties:", details['properties'])
        print("  Required:", details['required'])

    print("\nEdge Types:")
    for label, details in engine.ontology.edge_types.items():
        print(f"\n{label}:")
        print("  Properties:", details['properties'])
        print("  Required:", details['required'])

def add_node_type(engine):
    """Add a new node type to ontology"""
    label = input("Enter node type label: ")

    properties = {}
    while True:
        prop = input("Enter property name (or 'done' to finish): ")
        if prop.lower() == 'done':
            break
        prop_type = input(f"Enter type for {prop} (str/int/float/bool): ")
        properties[prop] = prop_type

    required = []
    while True:
        req = input("Enter required property name (or 'done' to finish): ")
        if req.lower() == 'done':
            break
        if req in properties:
            required.append(req)
        else:
            print("Property must be defined first!")

    engine.ontology.add_node_type(label, properties, required)
    print(f"Added node type: {label}")

def add_edge_type(engine):
    """Add a new edge type to ontology"""
    label = input("Enter edge type label: ")

    properties = {}
    while True:
        prop = input("Enter property name (or 'done' to finish): ")
        if prop.lower() == 'done':
            break
        prop_type = input(f"Enter type for {prop} (str/int/float/bool): ")
        properties[prop] = prop_type

    required = []
    while True:
        req = input("Enter required property name (or 'done' to finish): ")
        if req.lower() == 'done':
            break
        if req in properties:
            required.append(req)
        else:
            print("Property must be defined first!")

    engine.ontology.add_edge_type(label, properties, required)
    print(f"Added edge type: {label}")

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Determine database file path
    db_path = os.path.join(os.getcwd(), "test_graph.json") 
    print(f"Using local database file: {db_path}")

    # Setup ontology
    ontology = setup_ontology()

    # Initialize the ingestion engine.
    # Note: router_config is passed with a "db_path" key only;
    # our engine will detect this and assume a local backend.
    try:
        engine = IngestionEngine(
            router_config={"db_path": db_path},
            default_ontology=ontology,
            auto_extract_structured_data=True
        )
    except Exception as e:
        print(f"Failed to initialize IngestionEngine: {e}")
        return

    while True:
        print("\nIngestion Engine Test Console")
        print("1. Upload File")
        print("2. Search and Store")
        print("3. Handle Webhook")
        print("4. View Ontology")
        print("5. Add Node Type")
        print("6. Add Edge Type")
        print("7. Exit")

        choice = input("\nEnter your choice (1-7): ")

        try:
            if choice == "1":
                file_path = input("Enter file path: ")
                source_name = input("Enter data source name: ")
                try:
                    node_id = engine.upload_file(file_path, source_name)
                    print(f"File uploaded successfully. Node ID: {node_id}")
                except Exception as e:
                    logger.error(f"Error uploading file: {e}")

            elif choice == "2":
                query = input("Enter search query: ")
                try:
                    engine.search_and_store_results(query)
                    print("Search results stored successfully")
                except Exception as e:
                    logger.error(f"Error in search: {e}")

            elif choice == "3":
                try:
                    webhook_data = {
                        "event": input("Enter event type: "),
                        "payload": input("Enter payload: ")
                    }
                    source = input("Enter webhook source name: ")
                    engine.handle_webhook(webhook_data, source)
                    print("Webhook handled successfully")
                except Exception as e:
                    logger.error(f"Error handling webhook: {e}")

            elif choice == "4":
                print_ontology(engine)

            elif choice == "5":
                add_node_type(engine)

            elif choice == "6":
                add_edge_type(engine)

            elif choice == "7":
                print("Exiting...")
                break

            else:
                print("Invalid choice. Please try again.")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    try:
        main()
    finally:
        # Ensure the database is saved when exiting
        if 'engine' in globals() and hasattr(engine, 'db'):
            engine.db.disconnect()
