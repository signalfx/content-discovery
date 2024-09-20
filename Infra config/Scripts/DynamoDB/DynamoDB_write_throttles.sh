#!/bin/bash
TABLE_NAME=bits_metrics
# 3. Throttled Write Function with Exponential Backoff
write_with_throttle() {
  local retries=5
  local max_delay=30
  while true; do
    aws dynamodb put-item --table-name $TABLE_NAME --item file://item.json || {  # Replace with your item data
      if [[ $retries -gt 0 ]]; then
        sleep $((RANDOM % max_delay))
        retries=$((retries - 1))
        max_delay=$((max_delay * 2))  # Increase backoff exponentially
        echo "Write throttled, retrying in $max_delay seconds..."
      else
        echo "Write failed after retries, exiting..."
        exit 1
      fi
    }
    return 0  # Successful write
  done
}
# 4. Perform Write with Throttle Handling
write_with_throttle
echo "Write completed successfully!"