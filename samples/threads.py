import threading
import time
import signal

class MainThread(threading.Thread):
    def __init__(self):
       threading.Thread.__init__(self)
         
       # The shutdown_flag is a threading.Event object that
       # indicates whether the thread should be terminated.
       self.shutdown_flag = threading.Event()
        
    def run(self):
        print("Thread has started!")
        while not self.shutdown_flag.is_set():
            print("hello")
            time.sleep(1)

        print('Thread #%s stopped' % self.ident)

class ServiceExit(Exception):
    pass



def service_shutdown(signum, frame):
    print('Caught signal %d' % signum)
    raise ServiceExit

def main():
     
    # Register the signal handlers
    signal.signal(signal.SIGTERM, service_shutdown)
    signal.signal(signal.SIGINT, service_shutdown)

    print("Starting the example program")

    try:
        t=MainThread()
        u=MainThread()
        t.start()
        u.start()

        while True:
            time.sleep(0.5)

    except ServiceExit:
        # Terminate the running threads.
        # Set the shutdown flag on each thread to trigger a clean shutdown of each thread.
        t.shutdown_flag.set()
        u.shutdown_flag.set()
        # Wait for the threads to close...
        t.join()
        u.join()

    print('Exiting main program')
     
      
if __name__ == '__main__':
    main()
