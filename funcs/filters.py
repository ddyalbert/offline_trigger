import numpy as np
from scipy import signal

def bessel_filter(x, fs, fc = 100, order = 8, analog = False):
    # 对 x 进行Bessel 低通滤波
    if analog:
        b, a = signal.bessel(order, 2 * np.pi * fc,  btype='low', analog=True, norm='phase')
        sysd = signal.cont2discrete((b, a), dt=1/fs, method='bilinear')
        b, a = sysd[0].flatten(), sysd[1]
    else:
        b, a = signal.bessel(order, fc / (fs/2), btype='low', analog=False, norm='phase')
    
    
    y = signal.filtfilt(b, a, x)
    return y


def Hf_bessel(f, fs = 5000, fc = 100, order = 8, analog = False):
    # 计算 Bessel 低通滤波器的频率响应
    if analog:
        b, a = signal.bessel(order, 2 * np.pi * fc,  btype='low', analog=True, norm='phase')
        _, h = signal.freqs(b, a, worN=2 * np.pi * f)
    else:
        b, a = signal.bessel(order, fc / (fs/2), btype='low', analog=False, norm='phase')
        _, h = signal.freqz(b, a, worN=f, fs = fs)

    return h

def filterByHt(x, h, n_hmax = None):
    """
    y[N] = sum_p x[N+p] * H[p+n_max]
    一定要注意H的正反向
    """
    if n_hmax is None:
        n_hmax = np.argmax(h)
    y = signal.correlate(x, h, mode="full")
    y = y[len(h) - n_hmax - 1 : len(y) - n_hmax]

    return y

def Ht_Gaus(sigma, k = 5):
    sigma = int(sigma)
    t = np.arange(- k*sigma, k*sigma + 1)
    pp = (np.sqrt(2*np.pi) * sigma)
    g = np.exp(-t**2 / (2*sigma**2)) / pp
    return g

def Ht_DoG(sigma, k = 5):
    sigma = int(sigma)
    t = np.arange(- k*sigma, k*sigma + 1)
    g = t / sigma**2 * np.exp(-t**2 / (2*sigma**2))
    return g

