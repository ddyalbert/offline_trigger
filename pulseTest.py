import matplotlib.pyplot as plt
import pickle

import classes.pulseGenerator as pg
import classes.optimalFilter as OF
import classes.events as ev



# Load pulse data from file ---------------------------------------------------------------------
try:
    # raise FileNotFoundError
    with open('.temp/.pulse.pkl', 'rb') as f:
        mp: pg.MultiplePulse = pickle.load(f)
except:
    sp = pg.SinglePulse(sampling = 5000, tr = 0.01, td = 0.05, proportion = 1)
    sp.generate_pulse(duration = 2, start_time = 0.5)
    mp = pg.MultiplePulse(sp)
    mp.pulse_info.generate_pulse_info(duration = 5000, events_rate = 1/4, random_time_range= 0.5)
    mp.generate_multiple_pulses(is_recreate_pulse=True)
    
    mp.add_write_noise(0.050) # 热噪声
    mp.bessel_filter(cut_freq = 100, order=6, is_normalize=True) # Bessel 滤波器
    mp.add_write_noise(0.001) # ADC量化噪声
    mp.add_sin_noise(freq = 50, amp = 0.01)
    mp.add_sin_noise(freq = 12, amp = 0.002)
    mp.add_sin_noise(freq = 21, amp = 0.005)
    mp.add_sin_noise(freq = 76, amp = 0.002)

    mp.optimal_filter(win_len=2, is_from_data=True, is_hann_filter=False)
    with open('.temp/.pulse.pkl', 'wb') as f:
        pickle.dump(mp, f)


mp.optimal_filter(win_len=2, is_from_data=True, is_hann_filter=False)
mp.plot_pulse(100)
# mp.plot_noise_psd()

# mp.of.plot_freq_domain()
# mp.of.plot_time_domain(plot_type="")

# ---------------------------------------------------------------------------

def get_pulse_amplitude():
    amp = pg.PulseAmplitude()
    amp.get_pulse_amplitude(mp)
    amp.plot_amp_hist(["amp_raw", "amp_fil"])
def plot_bl_sigma():
    bl_sigma = ev.BaselineSigma(mp.of)
    bl_sigma.add_noise(mp.noise)
    bl_sigma.plot()


# get_pulse_amplitude()
# plot_bl_sigma()



input("Press Enter to continue...")
