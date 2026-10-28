### Exercise 02 case 1: valid customer + order pair (trusted context used)
POST http://127.0.0.1:8000/generate-response
Content-Type: application/json

{
  "customer_message": "Where is my order? It should have arrived by now.",
  "customer_id": "CUST-101",
  "order_id": "ORD-1001"
}
results
<img width="428" height="619" alt="image" src="https://github.com/user-attachments/assets/22057f32-3d15-4bf9-9a3a-ea3f585b437e" />



### Exercise 02 case 2: same order under a different customer (no trusted context)
POST http://127.0.0.1:8000/generate-response
Content-Type: application/json

{
  "customer_message": "Where is my order? It should have arrived by now.",
  "customer_id": "CUST-102",
  "order_id": "ORD-1001"
}

results 
<img width="413" height="658" alt="image" src="https://github.com/user-attachments/assets/bbe284e3-2e08-4b1f-b285-7eea1487ba02" />

### Exercise 02 case 3: order ID without customer ID (HTTP 422, no Claude call)
POST http://127.0.0.1:8000/generate-response
Content-Type: application/json

{
  "customer_message": "Where is my order? It should have arrived by now.",
  "order_id": "ORD-1001"
}
resuilts
<img width="417" height="574" alt="image" src="https://github.com/user-attachments/assets/ecb93a5b-b3b7-43fc-b426-a76c4d7c7b67" />



