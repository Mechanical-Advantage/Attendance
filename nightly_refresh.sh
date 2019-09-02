#!/bin/bash
#Cycle probemon log
echo 'Cycling monitor log'
cd '/home/attendance/Attendance_data/logs'
date=`date '+%m-%d-%Y at %I:%M:%S %p'`
cp 'monitor.log' "./monitor/$date.log"
echo '' > 'monitor.log'

#Cycle server log
echo 'Cycling server log'
cd '/home/attendance/Attendance_data/logs'
cp 'serverlog.log' "./serverlogs/$date.log"
echo '' > 'serverlog.log'

#Create backup
sizeLimit='28672' #in megabytes (1 gigabyte = 1024 megabytes); currently set at 28 gigabytes
targetPath='/media/jbonner/ATT_BACKUP'

cd '/home/attendance/'

#Create zip
echo 'Creating zip file...'
zip -r backup.zip Attendance_data > /dev/null

#Get size of data and calculate target size
du_output=`du -sb ./backup.zip`
du_array=($du_output)
dataSize=${du_array[0]}
targetSize=$(expr $sizeLimit \* 1048576 - $dataSize)

#Find current size
du_output=`du -sb "$targetPath"`
du_array=($du_output)
size=${du_array[0]}

while [ "$size" -gt "$targetSize" ]; do
#Delete oldest backup
filename=`ls -1r "$targetPath" | tail -n 1`
#Check if folder empty
if [ "$filename" == '' ]; then
echo 'Cannot create backup - capacity too small'
exit 1
fi

echo "Deleting backup '$filename'"
rm -r "$targetPath"/"$filename"

#Get new size
du_output=`du -sb "$targetPath"`
du_array=($du_output)
size=${du_array[0]}
done

echo 'Copying data...'
currentTime=`date '+%s - %m-%d-%Y'`
cp -r --no-preserve=mode ./backup.zip "$targetPath"/"$currentTime".zip
du -sh "$targetPath"

echo 'Deleting zip file...'
rm ./backup.zip
