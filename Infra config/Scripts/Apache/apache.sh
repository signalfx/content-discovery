
#!/bin/bash
#for i in {0..3}
#do
#ab -n 500000 -c 1000 http://localhost/mod_status?auto
#done
for i in {1..10};do ab -k -n 100000 -c 1000 http://localhost/;done
