"""
Training Service - Trains recommendation models using collaborative filtering.
Tracks experiments with MLflow and saves model artifacts.
"""

import os
import sys
import json
import pickle
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import numpy as np
import pandas as pd
import psycopg2
from sklearn.model_selection import train_test_split
import lightgbm as lgb
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import settings
from shared.logging_config import setup_logging

logger = setup_logging("trainer")


class RecommendationTrainer:
    """Trains recommendation models."""
    
    def __init__(self):
        """Initialize trainer."""
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        mlflow.set_experiment(settings.mlflow.experiment_name)
        self.client = MlflowClient()
    
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load training data from PostgreSQL.
        
        Returns:
            Tuple of (interactions_df, items_df)
        """
        logger.info("Loading training data from database...")
        
        conn = psycopg2.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.db,
            user=settings.database.user,
            password=settings.database.password
        )
        
        try:
            # Load interactions
            interactions_df = pd.read_sql(
                """
                SELECT user_id, item_id, interaction_type, count, last_interaction_at
                FROM interactions
                WHERE last_interaction_at > NOW() - INTERVAL '90 days'
                """,
                conn
            )
            
            # Load items
            items_df = pd.read_sql(
                """
                SELECT item_id, category, metadata
                FROM items
                """,
                conn
            )
            
            logger.info(f"Loaded {len(interactions_df)} interactions and {len(items_df)} items")
            return interactions_df, items_df
        
        finally:
            conn.close()
    
    def create_features(self, interactions_df: pd.DataFrame, items_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create features for training.
        
        Args:
            interactions_df: User-item interactions
            items_df: Item metadata
        
        Returns:
            Feature dataframe
        """
        logger.info("Creating features...")
        
        # Aggregate interactions by user-item pair
        user_item_features = interactions_df.groupby(['user_id', 'item_id']).agg({
            'count': 'sum',
            'interaction_type': lambda x: x.value_counts().to_dict(),
            'last_interaction_at': 'max'
        }).reset_index()
        
        # Merge with item features
        features_df = user_item_features.merge(items_df, on='item_id', how='left')
        
        # Create simple features
        features_df['days_since_interaction'] = (
            pd.to_datetime('now') - pd.to_datetime(features_df['last_interaction_at'])
        ).dt.days
        
        # Encode categories
        if 'category' in features_df.columns:
            features_df = pd.get_dummies(features_df, columns=['category'], prefix='cat')
        
        # Create target (binary: interaction exists = 1)
        features_df['target'] = 1
        
        return features_df
    
    def train_model(self, features_df: pd.DataFrame, test_size: float = 0.2) -> Dict:
        """
        Train LightGBM model.
        
        Args:
            features_df: Feature dataframe
            test_size: Test set proportion
        
        Returns:
            Dictionary with model and metrics
        """
        logger.info("Training model...")
        
        # Prepare features
        feature_cols = [col for col in features_df.columns 
                       if col not in ['user_id', 'item_id', 'target', 'last_interaction_at', 'interaction_type']]
        
        X = features_df[feature_cols].fillna(0)
        y = features_df['target']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Train model
        model = lgb.LGBMClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42,
            verbose=-1
        )
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            eval_metric='binary_logloss',
            callbacks=[lgb.early_stopping(stopping_rounds=10)]
        )
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        
        # Get feature importance
        feature_importance = dict(zip(feature_cols, model.feature_importances_))
        
        metrics = {
            'train_accuracy': float(train_score),
            'test_accuracy': float(test_score),
            'n_features': len(feature_cols),
            'n_samples_train': len(X_train),
            'n_samples_test': len(X_test),
        }
        
        logger.info(f"Model trained: test accuracy = {test_score:.4f}")
        
        return {
            'model': model,
            'metrics': metrics,
            'feature_cols': feature_cols,
            'feature_importance': feature_importance
        }
    
    def save_model(self, model: lgb.LGBMClassifier, feature_cols: List[str], run_id: str):
        """Save model artifact."""
        model_path = f"models/model_{run_id}.pkl"
        os.makedirs("models", exist_ok=True)
        
        model_data = {
            'model': model,
            'feature_cols': feature_cols,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {model_path}")
        return model_path
    
    def train_and_log(self) -> str:
        """
        Main training function with MLflow logging.
        
        Returns:
            Run ID
        """
        with mlflow.start_run() as run:
            logger.info(f"Starting MLflow run: {run.info.run_id}")
            
            # Load data
            interactions_df, items_df = self.load_data()
            
            # Create features
            features_df = self.create_features(interactions_df, items_df)
            
            # Train model
            result = self.train_model(features_df)
            model = result['model']
            metrics = result['metrics']
            feature_cols = result['feature_cols']
            
            # Log parameters
            mlflow.log_params({
                'n_estimators': 100,
                'learning_rate': 0.1,
                'max_depth': 5,
                'model_type': 'lightgbm'
            })
            
            # Log metrics
            mlflow.log_metrics(metrics)
            
            # Log model
            mlflow.sklearn.log_model(
                model,
                "model",
                registered_model_name="recommendation-model"
            )
            
            # Save model locally
            model_path = self.save_model(model, feature_cols, run.info.run_id)
            mlflow.log_artifact(model_path)
            
            # Log feature importance
            mlflow.log_dict(result['feature_importance'], "feature_importance.json")
            
            logger.info(f"Training complete. Run ID: {run.info.run_id}")
            
            return run.info.run_id


def main():
    """Main training entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Train recommendation model')
    parser.add_argument('--experiment-name', default=settings.mlflow.experiment_name)
    args = parser.parse_args()
    
    try:
        trainer = RecommendationTrainer()
        run_id = trainer.train_and_log()
        print(f"Training complete. Run ID: {run_id}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

