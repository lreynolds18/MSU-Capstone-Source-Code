import csv

#used to change the speed of a train
#takes in train ID and SPROG speed
#opens the train properties file, finds train, and changes its speed
class speedChanger:
    def __init__(self):
        a=0

    def changeSpeed(self, ID, speed):
        f = open('trainProperties.txt')
        oldFile = []

        #reader for the CSV file
        reader = csv.reader(f)


        # put old file into list
        for line in reader:
            oldFile.append(line)

        #print oldFile

        #change speed
        for item in oldFile:
            if item[0] == str(ID):
                item[1] = str(speed)
        
        f.close()


        ## Write to file
        writeFile = open('trainProperties.txt', 'w')
        write = csv.writer(writeFile)
        for line in oldFile:
            write.writerow(line)
        writeFile.close()

        return


