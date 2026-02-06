import numpy as np
import matplotlib.pyplot as plt
from numpy.typing import ArrayLike
from scipy.optimize import curve_fit


def _gauss_pdf(x, mu, sigma, A):
    return A / (sigma * np.sqrt(2*np.pi)) * np.exp(-(x - mu)**2 / (2*sigma**2))

def gauss_fit_hist(
        data: ArrayLike, 
        ax: plt.Axes, 
        binWidth: float = None, nBins: int = 50, mid: float = None,
        label='', color=None, 
        data_std: float = None, unit: str = ''
        ):
    
    if len(data) == 0:
        raise ValueError("Amplitude data is None. Please get pulse amplitude first.")
    if color is None:
        color = 'r'
    if mid is None:
        mid = np.mean(data)
    if data_std is None:
        data_std = np.std(data[np.abs(data-mid) < range])
    if binWidth is None:
        binWidth = data_std / 10

    range = nBins * binWidth

    counts , bins, _ = ax.hist(
        data, 
        bins=nBins, 
        alpha=0.6,                     
        range=(-range + mid, range + mid), 
        label=label, 
        color=color, 
        histtype='bar'
        )
    
    bin_centers = 0.5 * (bins[:-1] + bins[1:])

    # eps = 1e-12
    # sigma_y = 1.0 / np.sqrt(counts + eps)

    popt, _ = curve_fit( _gauss_pdf, bin_centers, counts,
        p0=[mid, np.std(data), np.max(counts)],
        # sigma=sigma_y,
        absolute_sigma=False
    )

    x = np.linspace(bins[0], bins[-1], nBins * 10)
    y = _gauss_pdf(x, *popt)

    sigma = popt[1]
    if unit == "V":
        sigma *= 1000
        unit = "mV"

    ax.plot(x, y, color = color, lw=2, label= label + fr': $\sigma={sigma:.3g}$'+ ' ' + unit)
    return sigma
