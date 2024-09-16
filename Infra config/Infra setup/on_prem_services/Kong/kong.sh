curl -i -X GET   --url http://localhost:8000   --header 'Host: backend-api.local'; done
for i in {1..10000}; do curl -i -X GET http://localhost:8000/mock; done
for i in {1..10000}; do curl -i -X GET   --url http://localhost:8000/aws-prod-price-check/Prod/check --header 'auth-token: bits-sec-token'; done
for i in {1..10000}; do curl -i -X GET   --url http://localhost:8000/backend-api; done


# auth error
for i in {1..20}; do curl -s -X GET   --url http://localhost:8000/admin-api; done

# auth api
for i in {1..20}; do curl -s -X GET   --url http://localhost:8000/admin-api --header 'Authorization: Basic Yml0czpteS1wYXNzd29yZAo='

#rate limit
for i in {1..20}; do curl localhost:8000/local-api; done

for i in {1..20}; do curl -s -X GET   --url http://localhost:8000/admin-api/* --header 'Authorization: Basic amJiaXRzOkNyZXN0QDEyMwo='; done