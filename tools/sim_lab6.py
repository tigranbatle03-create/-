# -*- coding: utf-8 -*-
"""Численная проверка схем ЛР6 (QAM) без графики: те же блоки, что в .grc."""
import math
import numpy as np
from gnuradio import gr, blocks, digital, channels, filter, analog
from gnuradio.filter import firdes

samp_rate, symb_rate = 2e6, 50e3
sps = int(samp_rate / symb_rate)  # 40


def grid(M):
    """Точки квадратной QAM как в ЛР: шаг 1, центр в нуле (для 16QAM: ±0.5, ±1.5)."""
    m = int(round(M ** 0.5))
    v = [x - (m - 1) / 2 for x in range(m)]
    return [a + 1j * b for a in v for b in v]


def const_obj(M):
    return digital.constellation_calcdist(grid(M), list(range(M)), 4, 1,
                                          digital.constellation.AMPLITUDE_NORMALIZATION)


def run(M=16, data=None, noise=0.0, F=0.0, ntaps=40, lb=None, fdev_hz=4e3, n=30000,
        rx_gain=1.0, symsync=False, norm_tx=True, delay=0):
    tb = gr.top_block()
    if data is None:
        data = np.random.default_rng(3).integers(0, M, 1000).tolist()
    src = blocks.vector_source_b(list(data) * (n // len(data) + 1), False)
    c2s = digital.chunks_to_symbols_bc(list(const_obj(M).points()) if norm_tx else grid(M), 1)
    rrc_tx = firdes.root_raised_cosine(sps, samp_rate, symb_rate, 0.4, ntaps)
    tx = filter.interp_fir_filter_ccf(sps, rrc_tx)
    ch = channels.channel_model(noise, F / samp_rate, 1.0, [1.0], 0)
    raw = blocks.vector_sink_c()
    tb.connect(src, c2s, tx, ch, raw)
    if symsync:
        taps = firdes.root_raised_cosine(128, 128 * sps, 1.0, 0.4, 11 * sps * 128)
        rx = digital.symbol_sync_cc(digital.TED_GARDNER, sps, 0.045, 1.0, 1.0, 1.5, 1,
                                    digital.constellation_16qam().base(), digital.IR_PFB_MF, 128, taps)
    else:
        rx = filter.fir_filter_ccf(sps, firdes.root_raised_cosine(rx_gain, samp_rate, symb_rate, 0.4, ntaps))
    if lb is None:
        lb = 4 / ((1 / math.sqrt(2)) * 5e-3 * symb_rate)
    fdev = 2 * math.pi * fdev_hz / symb_rate
    cr = digital.constellation_receiver_cb(const_obj(M).base(), lb, -fdev, fdev)
    s_out, s_err, s_sym, s_freq = blocks.vector_sink_b(), blocks.vector_sink_f(), blocks.vector_sink_c(), blocks.vector_sink_f()
    s_pre = blocks.vector_sink_c()
    if delay:
        dl = blocks.delay(gr.sizeof_gr_complex, delay)
        tb.connect(ch, dl, rx, cr)
    else:
        tb.connect(ch, rx, cr)
    tb.connect(rx, s_pre)
    tb.connect((cr, 0), s_out)
    tb.connect((cr, 1), s_err)
    tb.connect((cr, 3), s_freq)
    tb.connect((cr, 4), s_sym)
    tb.connect((cr, 2), blocks.null_sink(gr.sizeof_float))
    tb.run()
    out = np.array(s_out.data())
    tx_sym = np.array(list(data) * (n // len(data) + 1))[:n]
    # задержка тракта неизвестна – ищем по совпадению
    half = len(out) // 2
    pts0 = np.array(const_obj(M).points())
    best, ser, rot = 0, 1.0, 0
    for k in range(4):  # приёмник может захватить созвездие с поворотом на k*90°
        mp = np.array([np.argmin(np.abs(pts0 - p * (1j ** k))) for p in pts0])
        for d in range(0, 60):
            seg = out[half:half + 3000]
            ref = mp[tx_sym[half - d:half - d + 3000]]
            if len(seg) == len(ref):
                e = np.mean(seg != ref)
                if e < ser:
                    best, ser, rot = d, e, k * 90
    sym = np.array(s_sym.data())[half:]
    pts = np.array(const_obj(M).points())
    nearest = pts[np.argmin(np.abs(sym[:, None] - pts[None, :]), axis=1)]
    evm = np.sqrt(np.mean(np.abs(sym - nearest) ** 2) / np.mean(np.abs(pts) ** 2)) * 100
    return dict(ser=ser, rot=rot, out=out, evm=evm, err=np.array(s_err.data())[half:], freq=np.array(s_freq.data())[half:],
                raw=np.array(raw.data()), pre=np.array(s_pre.data())[half:], sym=sym)


def dE(M):
    p = np.array(const_obj(M).points())
    d = np.abs(p[:, None] - p[None, :])
    return d[d > 1e-9].min()


