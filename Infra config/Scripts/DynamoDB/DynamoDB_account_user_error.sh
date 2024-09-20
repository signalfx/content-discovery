

for i in {1..100}; do aws dynamodb query   --table-name bits_metrics123   --key-condition-expression "id = :id"; done