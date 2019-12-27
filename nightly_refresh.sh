#!/bin/bash
#Config
REPO_PATH='/home/attendance/Attendance'
DATA_PATH='/home/attendance/Attendance_data'
MAKE_BACKUP=true
BACKUP_PATH='/backup-usb'
SIZE_LIMIT='28672' #in megabytes

log () {
    echo [`date`] "$1" >> "$DATA_PATH/logs/refreshlog.log"
}

#Generate history cache
log 'Creating history cache'
python3.8 "$REPO_PATH/cache_history.py"

#Cycle server log
log 'Cycling server log'
cd "$DATA_PATH/logs"
cp 'serverlog.log' ./serverlogs/"`date`".log
echo '' > 'serverlog.log'

if [ "$MAKE_BACKUP" = true ]; then
    #Create zip
    cd ../..
    log 'Creating zip file'
    zip -r backup.zip "$DATA_PATH" > /dev/null

    #Get size of data and calculate target size
    du_output=`du -sb ./backup.zip`
    du_array=($du_output)
    dataSize=${du_array[0]}
    targetSize=$(expr $SIZE_LIMIT \* 1048576 - $dataSize)

    #Find current size
    du_output=`du -sb "$BACKUP_PATH"`
    du_array=($du_output)
    size=${du_array[0]}

    while [ "$size" -gt "$targetSize" ]; do
        #Delete oldest backup
        filename=`ls -1r "$BACKUP_PATH" | tail -n 1`
        #Check if folder empty
        if [ "$filename" == '' ]; then
            log 'Cannot create backup - capacity too small'
            exit 1
        fi

        log "Deleting backup '$filename'"
        rm -r "$BACKUP_PATH"/"$filename"

        #Get new size
        du_output=`du -sb "$BACKUP_PATH"`
        du_array=($du_output)
        size=${du_array[0]}
    done

    log 'Copying data'
    currentTime=`date '+%s - %m-%d-%Y'`
    cp -r --no-preserve=mode ./backup.zip "$BACKUP_PATH"/"$currentTime".zip
    du -sh "$BACKUP_PATH"

    log 'Deleting zip file'
    rm ./backup.zip
fi

log 'Finished refresh'

#Reboot once a week
if [ `date +%u` == 7 ]; then
    log 'Rebooting'
    reboot
fi