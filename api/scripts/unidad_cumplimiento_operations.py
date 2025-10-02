"""
Unidad Cumplimiento Operations
Operaciones específicas para el proyecto unidad-cumplimiento-aa245
Utiliza Workload Identity Federation para autenticación segura
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

# Import Firebase multi-project configuration
try:
    from database.firebase_config import (
        FirebaseManager, 
        get_unidad_cumplimiento_client,
        get_project_config,
        test_firebase_connection
    )
    FIREBASE_AVAILABLE = True
except Exception as e:
    print(f"Warning: Firebase import failed: {e}")
    FIREBASE_AVAILABLE = False

# ============================================================================
# UNIDAD CUMPLIMIENTO FIREBASE OPERATIONS
# ============================================================================

async def test_unidad_cumplimiento_connection() -> Dict[str, Any]:
    """Test connection to unidad-cumplimiento-aa245 Firebase project"""
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "connected": False,
            "error": "Firebase not available",
            "project": "unidad-cumplimiento-aa245"
        }
    
    try:
        # Test connection using project-specific client
        success, message = test_firebase_connection('unidad-cumplimiento')
        config = get_project_config('unidad-cumplimiento')
        
        return {
            "success": True,
            "connected": success,
            "message": message,
            "project_id": config['project_id'],
            "project_key": "unidad-cumplimiento",
            "environment": config['environment'],
            "timestamp": datetime.now().isoformat(),
            "authentication_method": "Workload Identity Federation" if config['environment'] == 'local' else "Service Account"
        }
        
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "error": f"Connection test failed: {str(e)}",
            "project": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat()
        }

async def get_unidad_cumplimiento_collections() -> Dict[str, Any]:
    """Get all collections from unidad-cumplimiento-aa245 project"""
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase not available",
            "collections": []
        }
    
    try:
        client = get_unidad_cumplimiento_client()
        if not client:
            return {
                "success": False,
                "error": "Could not connect to unidad-cumplimiento-aa245",
                "collections": []
            }
        
        # Get all collections
        collections = []
        collection_refs = client.collections()
        
        for collection_ref in collection_refs:
            try:
                # Get basic collection info
                collection_info = {
                    "name": collection_ref.id,
                    "path": collection_ref.path,
                    "documents_sample": []
                }
                
                # Get first 3 documents as sample
                docs = collection_ref.limit(3).stream()
                for doc in docs:
                    doc_data = doc.to_dict()
                    collection_info["documents_sample"].append({
                        "id": doc.id,
                        "fields": list(doc_data.keys()) if doc_data else [],
                        "sample_data": {k: str(v)[:50] + "..." if len(str(v)) > 50 else v 
                                      for k, v in (doc_data or {}).items()}
                    })
                
                collections.append(collection_info)
                
                # Add small delay to prevent overwhelming Firestore
                await asyncio.sleep(0.1)
                
            except Exception as collection_error:
                print(f"Error processing collection {collection_ref.id}: {collection_error}")
                collections.append({
                    "name": collection_ref.id,
                    "path": collection_ref.path,
                    "error": str(collection_error),
                    "documents_sample": []
                })
        
        return {
            "success": True,
            "collections": collections,
            "total_collections": len(collections),
            "project_id": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat(),
            "message": f"Found {len(collections)} collections in unidad-cumplimiento-aa245"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error getting collections: {str(e)}",
            "collections": [],
            "project_id": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat()
        }

async def get_unidad_cumplimiento_collection_data(
    collection_name: str,
    limit: Optional[int] = 100,
    offset: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Get data from a specific collection in unidad-cumplimiento-aa245"""
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase not available",
            "data": []
        }
    
    try:
        client = get_unidad_cumplimiento_client()
        if not client:
            return {
                "success": False,
                "error": "Could not connect to unidad-cumplimiento-aa245",
                "data": []
            }
        
        # Get collection reference
        collection_ref = client.collection(collection_name)
        
        # Apply filters if provided
        query = collection_ref
        applied_filters = {}
        
        if filters:
            for field, value in filters.items():
                if value is not None:
                    try:
                        query = query.where(field, '==', value)
                        applied_filters[field] = value
                    except Exception as filter_error:
                        print(f"Warning: Could not apply filter {field}={value}: {filter_error}")
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        documents = []
        doc_count = 0
        
        for doc in query.stream():
            doc_data = doc.to_dict()
            if doc_data:
                doc_data['_firestore_id'] = doc.id
                documents.append(doc_data)
                doc_count += 1
        
        return {
            "success": True,
            "data": documents,
            "count": doc_count,
            "collection": collection_name,
            "project_id": "unidad-cumplimiento-aa245",
            "filters_applied": applied_filters,
            "limit_applied": limit,
            "timestamp": datetime.now().isoformat(),
            "message": f"Retrieved {doc_count} documents from {collection_name}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error getting data from {collection_name}: {str(e)}",
            "data": [],
            "collection": collection_name,
            "project_id": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat()
        }

async def get_unidad_cumplimiento_dashboard_metrics() -> Dict[str, Any]:
    """Get dashboard metrics for unidad-cumplimiento-aa245 project"""
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase not available",
            "metrics": {}
        }
    
    try:
        client = get_unidad_cumplimiento_client()
        if not client:
            return {
                "success": False,
                "error": "Could not connect to unidad-cumplimiento-aa245",
                "metrics": {}
            }
        
        # Get basic project metrics
        metrics = {
            "project_info": {
                "project_id": "unidad-cumplimiento-aa245",
                "project_key": "unidad-cumplimiento",
                "connection_status": "connected",
                "timestamp": datetime.now().isoformat()
            },
            "collections_summary": {},
            "total_documents": 0,
            "data_quality": {}
        }
        
        # Get collections info
        collections = []
        collection_refs = client.collections()
        
        for collection_ref in collection_refs:
            try:
                # Count documents in collection (sample-based for performance)
                sample_docs = list(collection_ref.limit(1000).stream())
                doc_count = len(sample_docs)
                
                collection_metrics = {
                    "name": collection_ref.id,
                    "document_count": doc_count,
                    "sample_fields": []
                }
                
                # Analyze field structure from sample
                if sample_docs:
                    sample_doc = sample_docs[0].to_dict()
                    if sample_doc:
                        collection_metrics["sample_fields"] = list(sample_doc.keys())
                        collection_metrics["has_data"] = True
                    else:
                        collection_metrics["has_data"] = False
                else:
                    collection_metrics["has_data"] = False
                
                collections.append(collection_metrics)
                metrics["total_documents"] += doc_count
                
                # Small delay for performance
                await asyncio.sleep(0.1)
                
            except Exception as collection_error:
                print(f"Error analyzing collection {collection_ref.id}: {collection_error}")
                collections.append({
                    "name": collection_ref.id,
                    "document_count": 0,
                    "error": str(collection_error),
                    "has_data": False
                })
        
        metrics["collections_summary"] = {
            "total_collections": len(collections),
            "collections": collections,
            "collections_with_data": len([c for c in collections if c.get("has_data", False)])
        }
        
        # Data quality assessment
        metrics["data_quality"] = {
            "collections_analyzed": len(collections),
            "collections_with_documents": len([c for c in collections if c.get("document_count", 0) > 0]),
            "total_documents_analyzed": metrics["total_documents"],
            "assessment_timestamp": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "metrics": metrics,
            "project_id": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat(),
            "message": f"Dashboard metrics generated for unidad-cumplimiento-aa245"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating dashboard metrics: {str(e)}",
            "metrics": {},
            "project_id": "unidad-cumplimiento-aa245",
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def validate_unidad_cumplimiento_setup() -> Dict[str, Any]:
    """Validate that unidad-cumplimiento-aa245 is properly configured"""
    validation_results = {
        "setup_valid": False,
        "checks": {},
        "recommendations": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # Check 1: Firebase SDK availability
    validation_results["checks"]["firebase_sdk"] = {
        "status": FIREBASE_AVAILABLE,
        "message": "Firebase Admin SDK available" if FIREBASE_AVAILABLE else "Firebase Admin SDK not available"
    }
    
    if not FIREBASE_AVAILABLE:
        validation_results["recommendations"].append("Install firebase-admin: pip install firebase-admin")
        return validation_results
    
    # Check 2: Project configuration
    try:
        config = get_project_config('unidad-cumplimiento')
        validation_results["checks"]["project_config"] = {
            "status": config['project_id'] != 'your-project-id',
            "project_id": config['project_id'],
            "environment": config['environment'],
            "message": f"Project configured: {config['project_id']}"
        }
        
        if config['project_id'] == 'your-project-id':
            validation_results["recommendations"].append("Configure FIREBASE_PROJECT_ID_UNIDAD environment variable")
    except Exception as e:
        validation_results["checks"]["project_config"] = {
            "status": False,
            "message": f"Configuration error: {str(e)}"
        }
    
    # Check 3: Connection test
    try:
        connection_result = await test_unidad_cumplimiento_connection()
        validation_results["checks"]["connection"] = {
            "status": connection_result.get("connected", False),
            "message": connection_result.get("message", "Connection test failed")
        }
        
        if not connection_result.get("connected", False):
            validation_results["recommendations"].append("Run: gcloud auth application-default login")
            validation_results["recommendations"].append("Or configure service account credentials")
    except Exception as e:
        validation_results["checks"]["connection"] = {
            "status": False,
            "message": f"Connection test error: {str(e)}"
        }
    
    # Check 4: Firestore client
    try:
        client = get_unidad_cumplimiento_client()
        validation_results["checks"]["firestore_client"] = {
            "status": client is not None,
            "message": "Firestore client available" if client else "Firestore client not available"
        }
    except Exception as e:
        validation_results["checks"]["firestore_client"] = {
            "status": False,
            "message": f"Client error: {str(e)}"
        }
    
    # Overall validation
    all_checks_passed = all(check.get("status", False) for check in validation_results["checks"].values())
    validation_results["setup_valid"] = all_checks_passed
    
    if all_checks_passed:
        validation_results["message"] = "✅ unidad-cumplimiento-aa245 setup is valid and ready"
    else:
        validation_results["message"] = "❌ unidad-cumplimiento-aa245 setup needs configuration"
    
    return validation_results

# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

__all__ = [
    'test_unidad_cumplimiento_connection',
    'get_unidad_cumplimiento_collections', 
    'get_unidad_cumplimiento_collection_data',
    'get_unidad_cumplimiento_dashboard_metrics',
    'validate_unidad_cumplimiento_setup'
]