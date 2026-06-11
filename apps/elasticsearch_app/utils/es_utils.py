import logging
from typing import List, Dict, Any

from django.db import models
from django_elasticsearch_dsl import Document
from elasticsearch import ElasticsearchException
from elasticsearch_dsl.connections import get_connection

logger = logging.getLogger(__name__)

def get_index_name(document_class):
    # Try preferred _index._name first
    if hasattr(document_class, "_index") and hasattr(document_class._index, "_name"):
        return document_class._index._name
    # fallback to Index.name class attribute
    if hasattr(document_class, "Index") and hasattr(document_class.Index, "name"):
        return document_class.Index.name
    raise AttributeError("Cannot find index name for document class")


def set_nested_value(d: Dict, keys: List[str], value: Any) -> None:
    """
    Set a value in a nested dictionary given a list of keys.
    """
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


def build_es_partial_update_doc(doc_class: Document, instance: models.Model, fields: List[str]) -> dict:
    """
    Build a partial Elasticsearch document update dict dynamically.
    Supports basic, nested, and prepared fields.

    Args:
        doc_class: Document instance (e.g., JobPostDocument())
        instance: Django model instance (e.g., JobPostModel)
        fields: List of field names to sync

    Returns:
        dict: partial update body to send via ES `.update(index, id, body={"doc": ...})`
    """
    doc = {}

    for field in fields:
        method_name = f"prepare_{field}"
        if hasattr(doc_class, method_name):
            # Call prepare method (e.g., prepare_company)
            method = getattr(doc_class, method_name)
            doc[field] = method(instance)
        else:
            # Fallback to using model's raw value
            doc[field] = getattr(instance, field, None)

    return doc

def partial_update_es_document(index: str, doc_id: int, doc_data: dict) -> None:
    """
    Perform a partial update to a document in Elasticsearch.

    Args:
        index (str): The name of the Elasticsearch index.
        doc_id (int): The ID of the document to update.
        doc_data (dict): The partial data to update the document with.

    Raises:
        ElasticsearchException: If the update fails.
    """
    es = get_connection()
    try:
        logger.info(f"[ES Partial Update] Updating doc_id={doc_id} in index='{index}' with data={doc_data}")
        es.update(
            index=index,
            id=doc_id,
            body={"doc": doc_data}
        )
    except ElasticsearchException as e:
        logger.error(f"[ES Partial Update] Failed to update doc_id={doc_id} in index='{index}': {e}", exc_info=True)
        raise
    
def calculate_slice_indices(page=1, page_size=10, max_page_size=100):
    """Calculates start and end indices for list/query slicing based on pagination params."""
    page = max(1, page)
    page_size = min(max(1, page_size), max_page_size)
    start = (page - 1) * page_size
    end = start + page_size
    return start, end

