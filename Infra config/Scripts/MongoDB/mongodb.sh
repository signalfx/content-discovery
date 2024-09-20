echo "Deleting colletion data"
mongo --port 28018 --quiet --eval "db = db.getSiblingDB('test');db.restaurants.deleteMany({})"
echo "wait 5 sec"
sleep 5
echo "importing data on demod DB"
mongoimport --port 28018 --db test --collection restaurants --file /home/centos/data.json
echo "query data"
mongo --port 28018 --quiet --eval "db = db.getSiblingDB('test');db.restaurants.find().limit( 10 ).pretty();"
~                                                                                                             