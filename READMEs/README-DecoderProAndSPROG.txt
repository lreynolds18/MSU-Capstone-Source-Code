Troubleshooting steps for Decoder Pro and SPROG

Port not found:
1. This may take a few tries, Decoder Pro is finnicky sometimes.
2. The port you want to use is /dev/ttyAMA0 if the port is not found and takes you to the preferences page.
3. You can change the port to  /dev/ttyS0 and restart DP, but you will have to switch it back, which will make it work again.
4. Do NOT change it to /dev/ttyACM0, as that may mess up the power button

MAKE SURE YOU SHUT OFF THE SPROG BEFORE TURNING OFF THE PI, AND ONLY TURN ON THE SPROG WHEN THE PI IS FULLY ON
Otherwise, the SPROG may break itself
