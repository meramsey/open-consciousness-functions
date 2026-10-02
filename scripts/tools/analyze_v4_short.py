"""Direct acoustic measurements of supplied V4-short excerpts.

Research-only dependencies: numpy, scipy, soundfile. No reference audio is
copied, and no offsets are inferred for other recordings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.optimize import least_squares

PAIRS = [(39.75, 40.25), (79.25, 80.75), (158.05, 161.95), (198.0, 202.0), (317.95, 322.05)]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def db(value):
    return float(20 * np.log10(max(float(abs(value)), 1e-20)))


def projection(x, fs, frequency, start):
    t = np.arange(len(x)) / fs + start
    w = signal.windows.hann(len(x), sym=False)
    return 2 * np.sum(x * w * np.exp(-2j * np.pi * frequency * t)) / w.sum()


def peak(x, fs, target, radius=.3):
    w = signal.windows.hann(len(x), sym=False)
    spectrum = abs(np.fft.rfft(x * w))
    frequencies = np.fft.rfftfreq(len(x), 1/fs)
    indices = np.flatnonzero(abs(frequencies-target) <= radius)
    index = indices[np.argmax(spectrum[indices])]
    log = np.log(spectrum[index-1:index+2] + 1e-30)
    shift = .5 * (log[0]-log[2]) / (log[0]-2*log[1]+log[2])
    return float(frequencies[index] + shift * fs/len(x))


def tone_rows(x, fs, windows):
    rows = []
    for start, length in windows:
        block = signal.resample_poly(x[round(start*fs):round((start+length)*fs)], 1, 40, axis=0)
        low_fs = fs/40
        for family, pair in enumerate(PAIRS):
            for ear, frequency in enumerate(pair):
                channel = block[:, ear]
                fitted = peak(channel, low_fs, frequency)
                center = projection(channel, low_fs, frequency, start)
                lower_frequency = peak(channel, low_fs, frequency-2, radius=.12)
                upper_frequency = peak(channel, low_fs, frequency+2, radius=.12)
                lower = projection(channel, low_fs, frequency-2, start)
                upper = projection(channel, low_fs, frequency+2, start)
                u, lower_ratio = upper/center, lower/center
                am = (u + np.conj(lower_ratio))/2
                pm = (u - np.conj(lower_ratio))/2
                slow_u = projection(channel, low_fs, frequency+1/30, start)/center
                slow_l = projection(channel, low_fs, frequency-1/30, start)/center
                slow_am = (slow_u+np.conj(slow_l))/2
                slow_pm = (slow_u-np.conj(slow_l))/2
                other = projection(block[:, 1-ear], low_fs, frequency, start)
                rows.append({
                    'window_start_s': start, 'window_duration_s': length,
                    'family_center_hz': sum(pair)/2, 'ear': 'L' if ear==0 else 'R',
                    'frequency_hz': fitted, 'nominal_hz': frequency,
                    'carrier_rms_dbfs': db(center/np.sqrt(2)),
                    'carrier_phase_global_deg': float(np.angle(center, deg=True)),
                    'lower_sideband_hz': lower_frequency, 'upper_sideband_hz': upper_frequency,
                    'lower_spacing_hz': fitted-lower_frequency, 'upper_spacing_hz': upper_frequency-fitted,
                    'lower_rel_db': db(lower_ratio), 'upper_rel_db': db(u),
                    'sideband_phase_closure_deg': float(np.angle(u*lower_ratio, deg=True)),
                    'AM_fractional_depth': float(2*abs(am)),
                    'PM_small_signal_rad': float(2*abs(pm)),
                    'AM_phase_global_deg': float(np.angle(am, deg=True)),
                    'PM_phase_global_deg': float(np.angle(pm, deg=True)),
                    'slow_AM_30s_depth': float(2*abs(slow_am)),
                    'slow_AM_30s_phase_deg': float(np.angle(slow_am, deg=True)),
                    'slow_PM_30s_rad': float(2*abs(slow_pm)),
                    'total_resolved_tone_power_dbfs': float(10*np.log10(abs(center)**2/2*(1+abs(u)**2+abs(lower_ratio)**2+abs(slow_u)**2+abs(slow_l)**2))),
                    'cross_ear_same_frequency_rel_db': db(other/center),
                })
    return rows


def continuum(x, fs, start, length):
    block = x[round(start*fs):round((start+length)*fs)]
    f, p = signal.welch(block, fs, nperseg=131072, axis=0)
    _, cross = signal.csd(block[:,0], block[:,1], fs, nperseg=131072)
    coherence = abs(cross)**2 / np.maximum(p[:,0]*p[:,1],1e-30)
    # Auto-mask narrow peaks against a robust local spectral floor. Mask data
    # is saved; remaining smooth spectral humps are not forced to a color law.
    level = 10*np.log10(p.mean(axis=1)+1e-30)
    floor = signal.medfilt(level, kernel_size=151)
    mask = level-floor > 8
    mask = np.convolve(mask.astype(int), np.ones(7,dtype=int), mode='same') > 0
    rows=[]
    for lo,hi in [(20,60),(60,130),(130,230),(230,380),(380,500),(500,1000),(1000,2000),
                  (1000,5000),(2000,5000),(5000,10000),(10000,16000),(16000,20000)]:
        good=(f>=lo)&(f<hi)&~mask
        density=np.median(p[good],axis=1)
        slope=float(np.polyfit(np.log10(f[good]),10*np.log10(density+1e-30),1)[0])
        # Uniform Welch bins: masked lines contribute zero, not an interpolated
        # trapezoid across the hole (which would count excluded power again).
        rms = np.sqrt(np.sum(p[good], axis=0) * (f[1]-f[0]))
        rows.append({'start_s':start,'duration_s':length,'low_hz':lo,'high_hz':hi,
                     'L_RMS_dbfs':db(rms[0]),'R_RMS_dbfs':db(rms[1]),'fit_slope_db_decade':slope,
                     'median_coherence':float(np.median(coherence[good])),
                     'median_cross_phase_deg':float(np.median(np.angle(cross[good],deg=True))),
                     'masked_fraction':float(np.mean(mask[(f>=lo)&(f<hi)]))})
    # Third-octave bins preserve the actual curved spectral shape.
    shape=[]
    for center in [25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,
                   1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000]:
        band=(f>=center/2**(1/6))&(f<center*2**(1/6))&~mask
        shape.append({'start_s':start,'center_hz':center,
                      'continuum_density_dbfs_hz':float(np.median(level[band])),
                      'coherence':float(np.median(coherence[band]))})
    # Delay only on strong coherent continuum: line masks prevent carrier beat
    # trajectories from masquerading as a broadband interaural delay.
    good=(f>=500)&(f<=5000)&~mask&(coherence>.8)
    delay=None
    if good.sum()>20:
        phase=np.unwrap(np.angle(cross))
        fit=np.polyfit(f[good],phase[good],1,w=np.sqrt(coherence[good]))
        delay={'R_lag_us':float(-fit[0]/(2*np.pi)*1e6),
               'residual_deg_rms':float(np.sqrt(np.mean((phase[good]-np.polyval(fit,f[good]))**2))*180/np.pi),
               'coherent_bins':int(good.sum())}
    return rows,shape,delay


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fit_shape(rows):
    """Fit the smooth two-power-law model, not a piecewise-line corner."""
    centers = sorted({row['center_hz'] for row in rows if 100 <= row['center_hz'] <= 800})
    frequencies = np.array(centers)
    observed = np.array([np.mean([row['continuum_density_dbfs_hz'] for row in rows if row['center_hz'] == center]) for center in centers])

    def residual(params):
        peak_hz, rise, fall, offset = params
        a, b = rise/20, fall/20
        x_star = (-b/a)**(1/(2*b-2*a))
        ratio = frequencies/(peak_hz/x_star)
        predicted = -10*np.log10(ratio**(-2*a)+ratio**(-2*b)) + offset
        return predicted-observed

    results = {}
    for label, minimum_fall in [('unconstrained', -100), ('farfield_supported', -48)]:
        fit = least_squares(residual, [200, 20, max(-45, minimum_fall), -50], bounds=([50, .1, minimum_fall, -150], [500, 48, -.1, 0]))
        results[label] = dict(zip(['peak_hz','rise_db_per_decade','fall_db_per_decade','density_offset'], map(float,fit.x)))
        results[label]['residual_rms_db'] = float(np.sqrt(np.mean(residual(fit.x)**2)))
    return {'fit_band_hz': [100,800], 'model': 'smooth power-domain joined two slopes, peak-corrected', 'fits': results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--f10',type=Path,required=True)
    parser.add_argument('--f11',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    summary={'evidence_class':'measured directly from supplied V4-short reference excerpt',
             'offset_transfer_to_other_sources':False,'method':{
                 'tone_windows':'20s centered at 20,60,100,140,180,220,260,300,340s; edges 0-10 and final10s; high-resolution20-140,140-260,260-380s',
                 'tone_estimator':'Hann FFT log-quadratic peaks; coherent nominal-frequency projections in global excerpt time; AM/PM from upper and conjugate lower sideband ratios',
                 'bed_estimator':'Welch PSD; >8dB local narrow peaks masked; band and third-octave continuum saved; fits reported per band, not a global color',
                 'phase_caveat':'Different-frequency interaural carrier phase is time/beat dependent; meaningful comparisons are same-frequency leakage and modulation phase. Carrier phases saved, not claimed fixed IPD.'}}
    for name,path in [('F10',args.f10),('F11',args.f11)]:
        x,fs=sf.read(path,dtype='float32',always_2d=True)
        info=sf.info(path)
        summary[name]={'source_file':str(path),'sha256':sha(path),'sample_rate':fs,'channels':x.shape[1],
                       'encoding':info.subtype,'duration_s':len(x)/fs,
                       'peak_dbfs':db(np.max(abs(x))),'full_rms_dbfs_L_R':[db(v) for v in np.sqrt(np.mean(x*x,axis=0,dtype=np.float64))]}
        rows=[]
        shape=[]
        delays=[]
        for start in ([20,140,260] if name=='F10' else [20,180,340]):
            bands,third,delay=continuum(x,fs,start,100)
            rows.extend(bands)
            shape.extend(third)
            delays.append({'start_s':start,'delay_fit':delay})
        write_csv(args.output/f'{name.lower()}-continuum-bands.csv',rows)
        write_csv(args.output/f'{name.lower()}-continuum-shape.csv',shape)
        summary[name]['delay_fits']=delays
        if name == 'F10':
            summary[name]['bed_shape_fit'] = fit_shape(shape)
            for start in [20,140,260]:
                selected = [row for row in rows if row['start_s'] == start and not (row['low_hz'] == 1000 and row['high_hz'] == 5000)]
                summary[name].setdefault('masked_continuum_rms', []).append({'start_s': start, 'L_R_dbfs': [float(10*np.log10(sum(10**(row[ear+'_RMS_dbfs']/10) for row in selected))) for ear in ['L','R']]})
        envelopes=[]
        for start in np.arange(0,len(x)/fs-5,5):
            block=x[round(start*fs):round((start+5)*fs)]
            envelopes.append({'start_s':float(start),'rms_L_dbfs':db(np.sqrt(np.mean(block[:,0]**2))),
                              'rms_R_dbfs':db(np.sqrt(np.mean(block[:,1]**2))),
                              'stereo_correlation':float(np.corrcoef(block.T)[0,1])})
        write_csv(args.output/f'{name.lower()}-5s-envelope.csv',envelopes)
        if name=='F10':
            windows=[(center-10,20) for center in range(20,341,40)] + [(0,10),(len(x)/fs-10,10),(20,120),(140,120),(260,120)]
            tones=tone_rows(x,fs,windows)
            write_csv(args.output/'f10-carriers-sidebands.csv',tones)
            aggregates=[]
            normal=[row for row in tones if row['window_duration_s']==20]
            for family,pair in enumerate(PAIRS):
                channels=[]
                for ear in ['L','R']:
                    selected=[r for r in normal if r['family_center_hz']==sum(pair)/2 and r['ear']==ear]
                    channels.append({'ear':ear,'frequency_mean_hz':float(np.mean([r['frequency_hz'] for r in selected])),
                                     'frequency_peak_to_peak_hz':float(np.ptp([r['frequency_hz'] for r in selected])),
                                     'carrier_rms_mean_dbfs':float(np.mean([r['carrier_rms_dbfs'] for r in selected])),
                                     'carrier_level_peak_to_peak_db':float(np.ptp([r['carrier_rms_dbfs'] for r in selected])),
                                     'AM_depth_median':float(np.median([r['AM_fractional_depth'] for r in selected])),
                                     'PM_rad_median':float(np.median([r['PM_small_signal_rad'] for r in selected])),
                                     'phase_closure_median_deg':float(np.median([r['sideband_phase_closure_deg'] for r in selected]))})
                aggregates.append({'center_hz':sum(pair)/2,'channels':channels})
            summary[name]['tone_aggregates']=aggregates
            long_rows=[row for row in tones if row['window_duration_s']==120]
            power=[]
            for pair in PAIRS:
                selected=[row for row in long_rows if row['family_center_hz']==sum(pair)/2]
                power.append({'center_hz':sum(pair)/2,
                              'mean_family_power_dbfs':float(np.mean([row['total_resolved_tone_power_dbfs'] for row in selected])),
                              'carrier_power_dbfs':float(np.mean([row['carrier_rms_dbfs'] for row in selected]))})
            reference=next(row['mean_family_power_dbfs'] for row in power if row['center_hz']==80)
            for row in power:
                row['relative_family_power_db']=row['mean_family_power_dbfs']-reference
            summary[name]['long_window_family_power']=power
        else:
            block=signal.resample_poly(x[20*fs:140*fs],1,10,axis=0)
            peaks=[]
            for ear in range(2):
                frequencies,psd=signal.welch(block[:,ear],fs/10,nperseg=262144)
                local=signal.medfilt(10*np.log10(psd+1e-30),151)
                candidates,_=signal.find_peaks(10*np.log10(psd+1e-30)-local,height=12)
                selected=sorted([i for i in candidates if 30<frequencies[i]<600],key=lambda i:psd[i],reverse=True)[:18]
                peaks.extend({'ear':'L' if ear==0 else 'R','frequency_hz':float(frequencies[i]),
                              'density_dbfs_hz':float(10*np.log10(psd[i]))} for i in selected)
            write_csv(args.output/'f11-comparison-peaks.csv',peaks)
    (args.output/'measurements.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
