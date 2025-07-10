from django_elasticsearch_dsl import Document, fields, Index, GeoPoint
from django_elasticsearch_dsl.registries import registry
from .models import Listing

@registry.register_document
class ListingDocument(Document):
    media_link = fields.ObjectField()  # Or use fields.NestedField() if the JSON contains nested objects
    location = GeoPoint()  # Adding the geo_point field

    class Index:
        name = 'listings'  # Name of the Elasticsearch index

    class Django:
        model = Listing  # The model associated with this Document
        fields = [
            'name',
            'description',
            'display_name',
            'category',
            'status',
            'remarks',
            'contact_name',
            'contact_number',
            'latitude',  # Include latitude and longitude fields
            'longitude',
            'place',
        ]

    def save(self, **kwargs):
        # Combine latitude and longitude into a single location field
        if self.latitude is not None and self.longitude is not None:
            self.location = {
                "lat": self.latitude,
                "lon": self.longitude
            }
        else:
            self.location = None  # Or handle missing location appropriately

        super().save(**kwargs)
