for i in {0..50}
do
curl -u adminuser:****** -XGET --header 'Content-Type: application/json'  'https://search-product-catalogue-y7dxzvazmia2drv6fob2fzpnzu.us-west-1.es.amazonaws.com/web_logs3/_search?pretty' -d '{
"aggs": {
"city": {
"terms": {
"field": "geoip.city_name.keyword"
},
"aggs": {
"responses": {
"terms": {
"field": "response"
}
}
}
},
"responses": {
"terms": {
"field": "response"
}
}
}
}'
done