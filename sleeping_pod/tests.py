from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from elasticsearch import Elasticsearch
from django.conf import settings

class SleepingPodSearchViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.es = Elasticsearch(
            hosts=[settings.ELASTICSEARCH_HOST],
            http_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        )
        self.index = settings.ELASTICSEARCH_INDEX

        # Sample data in Elasticsearch
        self.sample_data = [
            {
                "id": 1,
                "name": "Pod A",
                "category": 2,
                "location": {"lat": 12.9716, "lon": 77.5946},
            },
            {
                "id": 2,
                "name": "Pod B",
                "category": 2,
                "location": {"lat": 13.0827, "lon": 80.2707},
            },
            {
                "id": 3,
                "name": "Office Space",
                "category": 1,
                "location": {"lat": 12.2958, "lon": 76.6394},
            },
        ]

        # Indexing sample data in Elasticsearch
        for doc in self.sample_data:
            self.es.index(index=self.index, id=doc["id"], body=doc)

        self.es.indices.refresh(index=self.index)  # Refresh index to make data searchable

    def tearDown(self):
        # Cleanup Elasticsearch index
        for doc in self.sample_data:
            self.es.delete(index=self.index, id=doc["id"], ignore=[404])

        self.es.indices.refresh(index=self.index)

    def test_sleeping_pod_search_success(self):
        url = '/api/v1/sleeping_pod/sleeping-pods/search/'
        payload = {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "date": "2025-02-03",
            "time": "14:00:00",
            "duration": 2,
            "list_of_pods": [
                {
                "type": "single",
                "number_of_pods": 5
                },
                {
                "type": "double",
                "number_of_pods": 3
                }
            ]
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("available_places", response.data)
        self.assertEqual(len(response.data["available_places"]), 1)
        self.assertEqual(response.data["available_places"][0]["name"], "Pod A")

    def test_sleeping_pod_search_no_results(self):
        url = '/api/v1/sleeping_pod/sleeping-pods/search/'
        payload = {
            "latitude": 9.9312,  # Far away from sample data
            "longitude": 76.2673,
            "date": "2025-02-03",
            "time": "14:00:00",
            "duration": 2,
            "list_of_pods": [
                {
                "type": "single",
                "number_of_pods": 5
                },
                {
                "type": "double",
                "number_of_pods": 3
                }
            ]
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_places"], [])

    def test_invalid_payload(self):
        url = '/api/v1/sleeping_pod/sleeping-pods/search/'
        payload = {"latitude": "invalid", "longitude": 77.5946}

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("latitude", response.data)  # Validation error
