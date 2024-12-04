import TimeTagger as TT
import matplotlib.pyplot as plt
import numpy as np

def main():

    server_ip = '192.168.1.8'
    server_port = 41101

    tagger = TT.createTimeTaggerNetwork(f'{server_ip}:{server_port}')
    print(f"Connected to Time Tagger server at {server_ip}:{server_port}")

    tts_instance = TT.TimeTagStream(tagger, int(500e3), [5])

    interval = 0.1 
    num_points = 100 
    counts = []  


    plt.ion()  
    fig, ax = plt.subplots()
    line, = ax.plot(counts, label="Channel 5 Counts")
    ax.set_ylim(0, 100)  
    ax.set_xlabel("Time (intervals)")
    ax.set_ylabel("Counts")
    ax.legend()

    try:
        while True:
            tts_instance.startFor(capture_duration=int(interval * 1E12))  # Interval in picoseconds
            tts_instance.waitUntilFinished()
            timetagstream = tts_instance.getData()
            channel_stamps = timetagstream.getChannels()
            counts.append(np.sum(channel_stamps == 5))  # Count events in channel 5
            if len(counts) > num_points:
                counts.pop(0)
            line.set_ydata(counts)
            line.set_xdata(range(len(counts)))
            ax.set_xlim(0, len(counts))  # Adjust X-axis as the data grows
            plt.pause(0.01)  # Pause to update the plot

    except KeyboardInterrupt:
        print("Live plotting stopped.")

    tts_instance.stop()
    plt.ioff()  # Disable interactive mode
    plt.show()    

if __name__ == "__main__":
    main()