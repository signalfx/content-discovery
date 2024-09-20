
#!/bin/bash
ab -n 1000 -c 100 -H "Accept-Encoding: gzip, deflate" -rk http://localhost/
echo "Wait for 5sec"
sleep 5
ab -n 1000 -c 100 -p /home/centos/jb.json -T application/json -rk http://localhost/