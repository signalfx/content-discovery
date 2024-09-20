#mongosh
echo "show dbs" | mongosh
#echo "exit" | mongosh
echo "use example2" | mongosh
echo "db.Employee.insertOne( { "Employeename2" : 4321, "EmployeeDepartment2": 6548 } )" | mongosh
echo "db.movie.insertOne({"name" : 12345})" | mongosh
echo "db.Sample.insertOne({"SampleValue2" : 255, "SampleValue2" : 6655443})" | mongosh
#echo "db.dropDatabase()" | mongosh
#echo "db.Sample.find()" | mongosh

echo "use example3" | mongosh
echo "db.Employee.insertOne( { "Employeename2" : 421, "EmployeeDepartment2": 648 } )" | mongosh
echo "db.movie.insertOne({"name" : 1235})" | mongosh
echo "db.Sample.insertOne({"SampleValue2" : 25, "SampleValue2" : 665543})" | mongosh
#echo "db.Sample.find()" | mongosh