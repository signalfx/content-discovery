#!/bin/bash

# 2. Table Name
echo `date`
TABLE_NAME=bits_metrics

# Define the number of items to generate
NUM_ITEMS=1000

# Create a function to generate random data for a given item
generate_item() {
  local item_id=$(uuidgen)
  local random_value=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
  aws dynamodb put-item \
    --table-name $TABLE_NAME \
    --item "{\"id\":{\"S\":\"$item_id\"}, \"random_value\":{\"S\":\"$random_value\"}}"
}

# Ingest NUM_ITEMS items in a loop
for i in $(seq 1 $NUM_ITEMS); do
  generate_item
done

echo "Data ingestion complete!"
echo `date`
