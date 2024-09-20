
#!/bin/bash
echo "Querying Sales"
PGPASSWORD='******'  psql -P pager=off -h prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d dev -p 5439  -c "select * from sales;"
echo "############################################################################################################################################################################"
PGPASSWORD='******'  psql -P pager=off -h prod-datalake.cduhvu3e0aia.us-west-1.redshift.amazonaws.com -U datalakeadmin -d dev -p 5439  -c "select * from users;"