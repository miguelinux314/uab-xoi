#!/usr/bin/python

import matplotlib
from matplotlib import pyplot as plt
import numpy as np
from random import randint

if __name__ == '__main__':
    x_values = list(np.linspace(0, 3000, 31)[2::2])
    y_values = [x*x/1000 + 728 + randint(0, 44) for x in x_values]

    FONTSIZE = 16
    plt.rcParams.update({
        "font.size": FONTSIZE,
        "axes.titlesize": FONTSIZE,
        "axes.labelsize": FONTSIZE,
        "xtick.labelsize": FONTSIZE,
        "ytick.labelsize": FONTSIZE,
        "legend.fontsize": FONTSIZE,
        "font.family": "sans-serif",
        "font.sans-serif": ["URW Gothic"],
    })
    
    plt.plot(x_values, y_values, "-o", color=[x/255 for x in (243,102,25)])
    
    plt.xticks(x_values, rotation=90)
    plt.yticks([x for x in range(0, 10001, 1000)])
    plt.ylim(0, 10000)
    
    plt.xlabel(r"MTU$_{HugeAntenna}$ (bytes)")
    plt.ylabel("Cost (Mar$/byte)")
    
    # plt.minorticks_on()
    plt.grid(visible=True, which="major", color="#666666", linestyle="-")
    plt.grid(visible=True, which="minor", color="#aaaaaa", linestyle="-", linewidth=0.5)
    
    plt.savefig("cost_plot.pdf", bbox_inches="tight")
