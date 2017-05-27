import csv

#sets the train config file to turn on the track/continue to run
class trainOn:
    def __init__(self):
        a=0


    def turnTrainOn(self):
        f = open('trainProperties.txt')
        oldFile = []

        #reader for the CSV file
        reader = csv.reader(f)


        # put old file into list
        for line in reader:
            oldFile.append(line)


        f.close()
        oldFile[0][0] = "True"

        writeFile = open('trainProperties.txt', 'w')
        write = csv.writer(writeFile)
        for line in oldFile:
            write.writerow(line)
        writeFile.close()

        return
