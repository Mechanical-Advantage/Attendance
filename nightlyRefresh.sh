#!/bin/bash
#Cycle probemon log
echo 'Cycling probemon log'
cd '/home/jaw99/python/probemon'
date=`date '+%m-%d-%Y at %I:%M:%S %p'`
cp 'probemon.log' "../../Attendance_data/logs/probemon/$date.log"
echo '' > 'probemon.log'

#Cycle server log
echo 'Cycling server log'
cd '/home/jaw99/Attendance_data/logs'
cp 'serverlog.log' "./serverlogs/$date.log"
echo '' > 'serverlog.log'

#Create backup
sizeLimit='28672' #in megabytes (1 gigabyte = 1024 megabytes); currently set at 28 gigabytes
targetPath='/media/jaw99/ATT_BACKUP'

cd '/home/jaw99/'

#Get size of data and calculate target size
du_output=`du -sb ./Attendance_data`
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
cp -r --no-preserve=mode ./Attendance_data "$targetPath"/"$currentTime"
du -sh "$targetPath"
