#Cycle probemon log
cd '/home/jaw99/python/probemon'
date=`date '+%m-%d-%Y at %I:%M:%S %p'`
cp 'probemon.log' "../../Attendance_data/logs/probemon/$date.log"
echo '' > 'probemon.log'

#Cycle server log
cd '/home/jaw99/Attendance_data/logs'
cp 'serverlog.log' "./serverlogs/$date.log"
echo '' > 'serverlog.log'
