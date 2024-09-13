curl -u 'adminuser:**********' -X POST "https://search-product-catalogue-y7dxzvazmia2drv6fob2fzpnzu.us-west-1.es.amazonaws.com/web_logs1/_delete_by_query?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
     "match_all": {}
    }
  }
}'