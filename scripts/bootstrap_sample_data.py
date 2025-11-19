#!/usr/bin/env python3
"""
Bootstrap script to initialize the recommendation system with sample data.
Creates sample users, items, and initial interactions for testing.
"""

import os
import sys
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg2
from pymongo import MongoClient
from redis import Redis

# Configuration from environment
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'recommendation_db'),
    'user': os.getenv('POSTGRES_USER', 'recommendation_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'recommendation_pass'),
}

MONGODB_CONFIG = {
    'host': os.getenv('MONGODB_HOST', 'localhost'),
    'port': int(os.getenv('MONGODB_PORT', 27017)),
    'database': os.getenv('MONGODB_DB', 'recommendation_events'),
    'username': os.getenv('MONGODB_USER', 'recommendation_user'),
    'password': os.getenv('MONGODB_PASSWORD', 'recommendation_pass'),
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
    'password': os.getenv('REDIS_PASSWORD', None),
}


def create_sample_users(count: int = 100) -> List[str]:
    """Create sample users in PostgreSQL."""
    print(f"Creating {count} sample users...")
    
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cur = conn.cursor()
    
    user_ids = []
    for i in range(1, count + 1):
        user_id = f"user_{i:03d}"
        user_ids.append(user_id)
        
        metadata = {
            'age': random.randint(18, 65),
            'gender': random.choice(['M', 'F', 'Other']),
            'location': random.choice(['US', 'UK', 'CA', 'AU', 'DE']),
        }
        
        cur.execute(
            """
            INSERT INTO users (user_id, metadata)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, json.dumps(metadata))
        )
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Created {len(user_ids)} users")
    return user_ids


def create_sample_items(count: int = 200) -> List[str]:
    """Create sample items in PostgreSQL."""
    print(f"Creating {count} sample items...")
    
    categories = ['electronics', 'books', 'clothing', 'food', 'sports', 'toys', 'home', 'beauty']
    
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cur = conn.cursor()
    
    item_ids = []
    for i in range(1, count + 1):
        item_id = f"item_{i:03d}"
        item_ids.append(item_id)
        
        category = random.choice(categories)
        title = f"Sample {category.title()} Product {i}"
        
        metadata = {
            'price': round(random.uniform(10.0, 500.0), 2),
            'rating': round(random.uniform(3.0, 5.0), 1),
            'in_stock': random.choice([True, False]),
        }
        
        cur.execute(
            """
            INSERT INTO items (item_id, title, category, metadata)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (item_id) DO NOTHING
            """,
            (item_id, title, category, json.dumps(metadata))
        )
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Created {len(item_ids)} items")
    return item_ids


def create_sample_interactions(user_ids: List[str], item_ids: List[str], count: int = 1000):
    """Create sample interactions between users and items."""
    print(f"Creating {count} sample interactions...")
    
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cur = conn.cursor()
    
    event_types = ['view', 'click', 'purchase', 'add_to_cart']
    
    interactions_created = 0
    for _ in range(count):
        user_id = random.choice(user_ids)
        item_id = random.choice(item_ids)
        event_type = random.choice(event_types)
        
        # Weight events: more views than purchases
        if event_type == 'purchase' and random.random() > 0.1:
            event_type = 'view'
        
        timestamp = datetime.now() - timedelta(days=random.randint(0, 30))
        
        cur.execute(
            """
            INSERT INTO interactions (user_id, item_id, interaction_type, count, last_interaction_at)
            VALUES (%s, %s, %s, 1, %s)
            ON CONFLICT (user_id, item_id, interaction_type)
            DO UPDATE SET count = interactions.count + 1, last_interaction_at = %s
            """,
            (user_id, item_id, event_type, timestamp, timestamp)
        )
        interactions_created += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Created {interactions_created} interactions")


def create_sample_events(user_ids: List[str], item_ids: List[str], count: int = 500):
    """Create sample events in MongoDB."""
    print(f"Creating {count} sample events in MongoDB...")
    
    client = MongoClient(
        host=MONGODB_CONFIG['host'],
        port=MONGODB_CONFIG['port'],
        username=MONGODB_CONFIG.get('username'),
        password=MONGODB_CONFIG.get('password'),
    )
    db = client[MONGODB_CONFIG['database']]
    events_collection = db['events']
    
    event_types = ['view', 'click', 'purchase', 'add_to_cart']
    events = []
    
    for _ in range(count):
        user_id = random.choice(user_ids)
        item_id = random.choice(item_ids)
        event_type = random.choice(event_types)
        
        timestamp = datetime.now() - timedelta(days=random.randint(0, 30))
        
        event = {
            'user_id': user_id,
            'item_id': item_id,
            'event_type': event_type,
            'timestamp': timestamp.isoformat(),
            'properties': {
                'session_id': f"session_{random.randint(1, 100)}",
                'page': random.choice(['home', 'product', 'search', 'category']),
            }
        }
        events.append(event)
    
    if events:
        events_collection.insert_many(events)
    
    client.close()
    
    print(f"✓ Created {len(events)} events in MongoDB")


def main():
    """Main bootstrap function."""
    print("=" * 60)
    print("Bootstrapping Recommendation System with Sample Data")
    print("=" * 60)
    
    try:
        # Test connections
        print("\nTesting database connections...")
        psycopg2.connect(**POSTGRES_CONFIG).close()
        print("✓ PostgreSQL connected")
        
        client = MongoClient(
            host=MONGODB_CONFIG['host'],
            port=MONGODB_CONFIG['port'],
            username=MONGODB_CONFIG.get('username'),
            password=MONGODB_CONFIG.get('password'),
        )
        client.admin.command('ping')
        client.close()
        print("✓ MongoDB connected")
        
        redis_client = Redis(**REDIS_CONFIG)
        redis_client.ping()
        print("✓ Redis connected")
        
        # Create sample data
        print("\nCreating sample data...")
        user_ids = create_sample_users(count=100)
        item_ids = create_sample_items(count=200)
        create_sample_interactions(user_ids, item_ids, count=1000)
        create_sample_events(user_ids, item_ids, count=500)
        
        print("\n" + "=" * 60)
        print("✓ Bootstrap complete!")
        print("=" * 60)
        print(f"\nSample data created:")
        print(f"  - {len(user_ids)} users")
        print(f"  - {len(item_ids)} items")
        print(f"  - 1000 interactions")
        print(f"  - 500 events")
        
    except Exception as e:
        print(f"\n✗ Error during bootstrap: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

