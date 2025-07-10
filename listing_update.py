import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travloungev1.settings.dev')
django.setup()


from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, bulk
from listing.models import Listing_images, Listing_category

# Initialize Elasticsearch client
es = Elasticsearch(["http://95.217.186.74:9200"])

# Specify the index name
INDEX_NAME = "listings"

# Define the extra fields to add
# EXTRA_FIELDS = {
#     "images": "value1",
#     "cat_name": "value2",
# }

def get_all_documents(index_name):
    """Retrieve all documents from the specified Elasticsearch index."""
    try:
        # Use scan to iterate over all documents in the index
        documents = scan(es, index=index_name, query={"query": {"match_all": {}}})
        return [doc for doc in documents]
    except Exception as e:
        print(f"Error retrieving documents: {e}")
        return []

def update_documents_with_extra_fields(index_name, final_out):
    """Update documents by adding extra fields."""
    try:
        # Prepare the bulk update payload
        actions = [
            {
                "_op_type": "update",
                "_index": index_name,
                "_id": doc["_id"],
                "doc": {
                    "images": doc['images'],
                    "cat_title": doc['cat_title'],
                },
            }
            for doc in final_out
        ]

        # Perform the bulk update
        response = bulk(es, actions)
        print(response)

        print(f"Successfully updated {len(actions)} documents with extra fields.")
    except Exception as e:
        print(f"Error updating documents: {e}")

def get_images(list_ids):
    images = Listing_images.objects.filter(listing_id__in=list_ids)
    listing_image_dict = {}
    for img in images:
        if img.listing.id not in listing_image_dict.keys():
            listing_image_dict[img.listing.id] = []
            listing_image_dict[img.listing.id].append(img.image)
        else:
            listing_image_dict[img.listing.id].append(img.image)
    return listing_image_dict

def get_cat_title(cat_ids):
    categories = Listing_category.objects.filter(id__in=cat_ids)
    cat_dict = {}
    for cat in categories:
        cat_dict[cat.id] = cat.category_name
    return cat_dict

if __name__ == "__main__":
    # Step 1: Retrieve all documents from the index
    all_documents = get_all_documents(INDEX_NAME)

    if not all_documents:
        print("No documents found or error in fetching documents.")
    else:
        print(f"Retrieved {len(all_documents)} documents from the index.")
        # print(all_documents[0])
        cat_ids = []
        list_ids = []
        for doc in all_documents:
            doc['_id'] = int(doc['_id'])
            cat_id = doc['_source']['category']
            cat_ids.append(cat_id)

            list_id = doc['_id']
            list_ids.append(list_id)
        
        cat_ids = list(set(cat_ids))
        list_ids = list(set(list_ids))

        images = get_images(list_ids)
        cat_titles = get_cat_title(cat_ids)
        final_out = []
        for doc in all_documents:
            temp_dict = {}
            temp_dict['_id'] = doc['_id']
            source = doc['_source']
            temp_dict['cat_title'] = cat_titles[doc['_source']['category']]
            if doc['_id'] in images.keys():
                temp_dict['images'] = images[doc['_id']]
            else:
                temp_dict['images'] = []
            final_out.append(temp_dict)
        # print(final_out)

        # Step 2: Update each document with the extra fields
        update_documents_with_extra_fields(INDEX_NAME, final_out)
