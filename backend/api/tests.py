from django.test import TestCase


class HelloApiTest(TestCase):
    def test_hello(self):
        res = self.client.get('/api/hello/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('message', res.json())

    def test_cors_allows_frontend(self):
        res = self.client.get('/api/hello/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(res['Access-Control-Allow-Origin'], 'http://localhost:5173')
