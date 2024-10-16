import functools
import inspect
import math
import threading
import time
from typing import Callable, List

import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from memory_profiler import memory_usage


class Counter:
    def __init__(self):
        self.__count = 0

    def increment(self):
        self.__count += 1

    @property
    def count(self):
        return self.__count


def time_and_space_profiler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        mem_before = memory_usage()[0]

        counter = Counter()
        if 'compare_counter' in (inspect.getfullargspec(func).args + inspect.getfullargspec(func).kwonlyargs):
            kwargs['compare_counter'] = counter
        _result = func(*args, **kwargs)

        mem_after = memory_usage()[0]
        end_time = time.time()

        return counter.count, end_time - start_time, mem_after - mem_before

    return wrapper


class Profiler:
    def __init__(self):
        self.sizes: list[int] = []
        self.samples: int = 0
        self.__functions: list[Callable] = []
        self.__fig: matplotlib.figure.Figure | None = None
        self.__axs: List[List[matplotlib.axes.Axes]] | None = None

        self.__comparison_dataframe = pd.DataFrame()
        self.__time_dataframe = pd.DataFrame()
        self.__memory_dataframe = pd.DataFrame()
        self.__dataframe_semaphore: threading.Semaphore = threading.Semaphore()

    def add_size(self, size: int):
        self.sizes.append(size)
        self.sizes.sort()

    def set_samples(self, samples: int):
        if samples <= 0:
            raise ValueError("Samples must be greater than 0")
        self.samples = samples

    def add_function(self, func):
        self.__functions.append(
            time_and_space_profiler(func)
        )

    def set_functions(self, functions: list[Callable]):
        self.__functions = list(
            map(
                lambda f: time_and_space_profiler(f) if callable(f) else None,
                functions
            )
        )

    def show_functions(self):
        return self.__functions

    def run(self):
        self.__comparison_dataframe = pd.DataFrame({
            f"{f.__name__}_{s}": [0] * self.samples
            for f in self.__functions
            for s in self.sizes
        })
        self.__time_dataframe = pd.DataFrame({
            f"{f.__name__}_{s}": [.0] * self.samples
            for f in self.__functions
            for s in self.sizes
        })
        self.__memory_dataframe = pd.DataFrame({
            f"{f.__name__}_{s}": [.0] * self.samples
            for f in self.__functions
            for s in self.sizes
        })

        lists = {str(size): [] for size in self.sizes}
        xs = {str(size): [] for size in self.sizes}
        for size in self.sizes:
            for _ in range(self.samples):
                lists[str(size)].append(
                    np.sort(np.random.randint(0, size * 10, size)).tolist()
                )
                xs[str(size)].append(
                    np.random.randint(
                        -2 * int(math.log2(size)),
                        10 * size + 2 * int(math.log2(size))
                    )
                )

        threads = []
        for func in self.__functions:
            thread = threading.Thread(target=self.__runner, args=(func, lists, xs))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def __runner(self, func, arrays, x_values):
        threads: list[threading.Thread] = []
        for s in self.sizes:
            for i in range(self.samples):
                thread = threading.Thread(target=self.__sub_runner, args=(func, arrays[str(s)][i], x_values[str(s)][i], i, s))
                threads.append(thread)
        for t in threads:
            t.start()
            t.join()

    def __sub_runner(self, func, array, x, index, size):
        result = func(array, x)
        self.__dataframe_semaphore.acquire()
        self.__comparison_dataframe[f"{func.__name__}_{size}"][index] = result[0]
        self.__time_dataframe[f"{func.__name__}_{size}"][index] = result[1]
        self.__memory_dataframe[f"{func.__name__}_{size}"][index] = math.fabs(result[2])
        self.__dataframe_semaphore.release()

    def show(self):
        self.__fig, self.__axs = plt.subplots(2,2)
        for func in self.__functions:
            yc = [self.__comparison_dataframe[f"{func.__name__}_{s}"].mean() for s in self.sizes]
            yt = [self.__time_dataframe[f"{func.__name__}_{s}"].mean() * 1000 for s in self.sizes]
            ym = [self.__memory_dataframe[f"{func.__name__}_{s}"].mean() * 1000 for s in self.sizes]

            self.__axs[0, 0].plot(range(len(self.sizes)), yc, label=func.__name__)
            self.__axs[0, 1].plot(range(len(self.sizes)), yt, label=func.__name__)
            self.__axs[1, 0].plot(range(len(self.sizes)), ym, label=func.__name__)

        self.__axs[0, 0].set_yscale("log")
        self.__axs[0, 0].set_xticklabels([str(s) for s in self.sizes])
        self.__axs[0, 0].set_xticks(range(len(self.sizes)))
        self.__axs[0, 0].xaxis.set_tick_params(rotation=30, labelsize=10)
        self.__axs[0, 0].set_title("Comparison")
        self.__axs[0, 0].set_xlabel("Size")
        self.__axs[0, 0].yaxis.set_major_formatter(lambda x, _: f"{x:4}")
        self.__axs[0, 0].set_ylabel("Comparisons")

        self.__axs[0, 1].set_xticklabels([str(s) for s in self.sizes])
        self.__axs[0, 1].set_xticks(range(len(self.sizes)))
        self.__axs[0, 1].xaxis.set_tick_params(rotation=30, labelsize=10)
        self.__axs[0, 1].set_title("Time")
        self.__axs[0, 1].set_xlabel("Size")
        self.__axs[0, 1].yaxis.set_major_formatter(lambda x, _: f"{x:4}")
        self.__axs[0, 1].yaxis.set_minor_formatter(lambda x, _: f"{x:4}")
        self.__axs[0, 1].set_ylabel("Time (ms)")

        self.__axs[1, 0].set_xticklabels([str(s) for s in self.sizes])
        self.__axs[1, 0].set_xticks(range(len(self.sizes)))
        self.__axs[1, 0].xaxis.set_tick_params(rotation=30, labelsize=10)
        self.__axs[1, 0].set_title("Memory")
        self.__axs[1, 0].set_xlabel("Size")
        self.__axs[1, 0].yaxis.set_major_formatter(lambda x, _: f"{x:4}")
        self.__axs[1, 0].yaxis.set_minor_formatter(lambda x, _: f"{x:4}")
        self.__axs[1, 0].set_ylabel("Memory (KB)")

        self.__axs[1, 1].axis("off")
        self.__axs[1, 1].legend(
            tuple(self.__axs[0, 0].get_lines()),
            tuple(func.__name__ for func in self.__functions),
            loc="center")
        plt.tight_layout()
        plt.show()
