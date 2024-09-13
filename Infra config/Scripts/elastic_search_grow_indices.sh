curl -u adminuser:******** -XPOST --header 'Content-Type: application/json' https://search-product-catalogue-y7dxzvazmia2drv6fob2fzpnzu.us-west-1.es.amazonaws.com/_reindex -d '{
"source": {
"index": "web_logs"
},
"dest": {
"index": "index-000001"
}
}'