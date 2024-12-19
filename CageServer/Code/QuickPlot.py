import matplotlib.pyplot as plt 
  
  
fileName = 'running.txt'
x = []
y1 = []
y2 = []
y3 = []
xTitle = ''
yTitle = ''

first = True

for line in open('SpikesData/' + fileName, 'r'):
    lines = [i for i in line.split(',')]
    if first:
        print(lines)
        first = False
        xTitle = lines[0]
        yTitle = lines[1]
    else:
        x.append(float(lines[0]))
        y1.append(float(lines[1]))
        # y2.append(float(lines[2]))
        y3.append(float(lines[2].strip('\n')))
      
plt.title("Outliers") 
plt.xlabel(xTitle) 
plt.ylabel(yTitle)
plt.subplot(2, 1, 1)
plt.plot(x, y1)
plt.subplot(2, 1, 2)
plt.plot(x, y3)
# plt.subplot(3, 1, 3)
# plt.plot(x, y3) 
  
plt.show()
