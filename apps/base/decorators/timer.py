from functools import wraps
import time

def timer(func):
    """
        check  function performance 
        ex:
            
            @timer
            def a():
                do something
                
    """
    @wraps(func)  
    def wrapper(*args, **kwargs):
        start = time.time()

        result = func(*args, **kwargs)
        
        print('view {} takes {:.2f} ms'.format(func.__name__, (time.time() - start) * 1000))
        return result
    return wrapper

