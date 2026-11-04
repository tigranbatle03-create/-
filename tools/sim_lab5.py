# -*- coding: utf-8 -*-
"""Численная проверка схем ЛР5 без графики (те же блоки, вместо QT-sink – vector sink)."""
import cmath
import math
import numpy as np
from gnuradio import gr, blocks, digital, channels, analog, filter
from gnuradio.filter import firdes

samp_rate, sps, alpha = 2e6, 10, 0.4
NS = 20000  # символов


def dqpsk(vec, noise_mv=0.0, f_hz=0.0, n=4000):
    tb = gr.top_block()
    src = blocks.vector_source_b(list(vec) * (n // len(vec)), False)
    enc = digital.diff_encoder_bb(4, digital.DIFF_DIFFERENTIAL)
    c2s = digital.chunks_to_symbols_bc([0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j], 1)
    ch = channels.channel_model(noise_mv * 1e-3, f_hz / samp_rate, 1.0, [1.0], 0)
    dph = digital.diff_phasor_cc()
    cst = digital.constellation_calcdist([1, 1j, -1, -1j], [0, 1, 2, 3], 4, 1,
                                         digital.constellation.AMPLITUDE_NORMALIZATION).base()
    dec = digital.constellation_decoder_cb(cst)
    s_tx, s_ph, s_rx = blocks.vector_sink_b(), blocks.vector_sink_c(), blocks.vector_sink_b()
    tb.connect(src, enc, c2s, ch, dph, dec, s_rx)
    tb.connect(src, s_tx)
    tb.connect(dph, s_ph)
    tb.run()
    tx, rx = np.array(s_tx.data()), np.array(s_rx.data())
    ph = np.degrees(np.angle(np.array(s_ph.data())))
    # канал вносит задержку на несколько отсчётов – выравниваем
    best = min(range(0, 20), key=lambda d: np.mean(tx[20:len(rx) - d] != rx[20 + d:]))
    ser = np.mean(tx[20:len(rx) - best] != rx[20 + best:])
    return ser, ph


def mpsk(M=2, ted=digital.TED_EARLY_LATE, resamp=digital.IR_MMSE_8TAP, sync="costas",
         noise=0.0, foff_hz=0.0, fll=False, osps=1, const=None, diff=False, vec=None,
         loop_bw=alpha, nsym=NS):
    tb = gr.top_block()
    if const is None:
        const = {2: digital.constellation_bpsk(), 4: digital.constellation_qpsk(),
                 8: digital.constellation_8psk()}[M]
    k = int(math.log2(M))
    if vec is None:
        rng = np.random.default_rng(1)
        bits = rng.integers(0, 2, nsym * k).tolist()
        src = blocks.vector_source_b(bits, False)
        pack = blocks.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
    else:
        src = blocks.vector_source_b(list(vec) * (nsym // len(vec)), False)
        pack = blocks.unpacked_to_packed_bb(k, gr.GR_MSB_FIRST)
    mod = digital.generic_mod(const, diff, sps, True, alpha, False, False)
    ch = channels.channel_model(noise, foff_hz / samp_rate, 1.0, [1.0], 0)
    chain = [src, pack, mod, ch]
    if fll:
        chain.append(digital.fll_band_edge_cc(sps, alpha, 44, 2 * math.pi / 100))
    taps = firdes.root_raised_cosine(128, 128 * sps, 1.0, alpha, 11 * sps * 128) \
        if resamp == digital.IR_PFB_MF else []
    ss = digital.symbol_sync_cc(ted, sps, loop_bw, 1.0, 1.0, 1.5, osps, const.base(), resamp, 128, taps)
    chain.append(ss)
    if sync == "coarse":
        mul = blocks.multiply_cc()
        pll = analog.pll_carriertracking_cc(2 * math.pi / 100, 0.7, -0.7)
        for c in chain[:-1]:
            pass
        tb.connect(*chain)
        tb.connect(ss, (mul, 0))
        tb.connect(ss, (mul, 1))
        tb.connect(mul, pll)
        out = pll
    else:
        cos = digital.costas_loop_cc(2 * math.pi / 100, M, False)
        chain.append(cos)
        tb.connect(*chain)
        out = cos
    so = blocks.vector_sink_c()
    tb.connect(out, so)
    res = {}
    if vec is not None:
        dec = digital.constellation_decoder_cb(const.base())
        sd = blocks.vector_sink_b()
        if diff:
            dd = digital.diff_decoder_bb(M, digital.DIFF_DIFFERENTIAL)
            tb.connect(out, dec, dd, sd)
        else:
            tb.connect(out, dec, sd)
        res["dec"] = sd
    tb.run()
    y = np.array(so.data())
    y = y[len(y) // 2:]
    if osps > 1:
        y = y[::osps]
    # EVM по фазе: отклонение угла от ближайшей точки M-PSK (на выходе x² точки удваиваются)
    Meff = 1 if sync == "coarse" else M
    ang = np.angle(y) * Meff
    err = np.angle(np.exp(1j * (ang - np.round(ang / (2 * np.pi)) * 2 * np.pi)))  # вокруг 0
    # фаза Костаса для 8PSK/QPSK может стоять со сдвигом – берём отклонение от ближайшей точки
    q = 2 * np.pi / M
    ph = np.angle(y) - (np.angle(const.points()[0]) % q)
    e = (ph - np.round(ph / q) * q) if sync != "coarse" else err
    res["phase_rms_deg"] = float(np.degrees(np.sqrt(np.mean(e ** 2))))
    res["amp_cv"] = float(np.std(np.abs(y)) / np.mean(np.abs(y)))
    if vec is not None:
        d = np.array(res["dec"].data())
        res["dec_tail"] = d[-12:].tolist()
        vals, cnt = np.unique(d[len(d) // 2:], return_counts=True)
        res["dec_hist"] = dict(zip(vals.tolist(), cnt.tolist()))
        del res["dec"]
    return res


if __name__ == "__main__":
    print("=== Часть 1. DQPSK")
    ser, ph = dqpsk((0, 1, 2, 3))
    print("алфавит 0..3: SER =", ser, " приращения фаз, град:", np.round(ph[1:9]).tolist())
    ser, ph = dqpsk((2,))
    print("один символ 2: SER =", ser, " приращение:", np.round(ph[1:5]).tolist())
    for f in (1e3, 5e3, 10e3):
        ser, ph = dqpsk((0, 1, 2, 3), f_hz=f)
        print(f"расстройка {f/1e3:.0f} кГц: SER = {ser:.4f}, поворот приращения = {np.mean(ph[1::4]):.1f}° (теор. {360*f/samp_rate:.1f}°)")
    for nmv in (100, 200, 300, 350, 400, 450, 500, 600, 700):
        ser, _ = dqpsk((0, 1, 2, 3), noise_mv=nmv, n=40000)
        print(f"шум {nmv} мВ: SER = {ser:.5f}")

    print("=== Часть 2. BPSK, грубая (x²+PLL) vs Костас")
    print("coarse", mpsk(2, sync="coarse"))
    print("costas", mpsk(2))
    print("=== 2.7.3 TED при шуме 50 мВ и 100 мВ (BPSK, MMSE)")
    teds = {"Mueller&Muller": digital.TED_MUELLER_AND_MULLER,
            "Mod. M&M": digital.TED_MOD_MUELLER_AND_MULLER,
            "Zero Crossing": digital.TED_ZERO_CROSSING, "Gardner": digital.TED_GARDNER,
            "Early-Late": digital.TED_EARLY_LATE,
            "Signal x Slope ML": digital.TED_SIGNAL_TIMES_SLOPE_ML,
            "Signum x Slope ML": digital.TED_SIGNUM_TIMES_SLOPE_ML}
    for nv in (0.05, 0.1):
        for name, t in teds.items():
            r = mpsk(2, ted=t, noise=nv)
            print(f"  noise={nv}: {name:18s} фазовая RMS = {r['phase_rms_deg']:.2f}°  CV|y| = {r['amp_cv']:.3f}")
    print("=== 2.7.5 интерполяторы (Gardner, шум 50 мВ)")
    for name, rt in (("MMSE 8 tap", digital.IR_MMSE_8TAP), ("PFB no MF", digital.IR_PFB_NO_MF),
                     ("PFB MF", digital.IR_PFB_MF)):
        r = mpsk(2, ted=digital.TED_GARDNER, resamp=rt, noise=0.05)
        print(f"  {name:10s} фазовая RMS = {r['phase_rms_deg']:.2f}°  CV|y| = {r['amp_cv']:.3f}")
    print("=== 2.7.6 QPSK")
    print(mpsk(4, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, noise=0.0))
    print("=== 2.7.7 расстройка N*10 кГц")
    for N in (1, 2, 3, 5):
        a = mpsk(4, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=N * 10e3)
        b = mpsk(4, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=N * 10e3, fll=True)
        print(f"  N={N}: только Костас RMS={a['phase_rms_deg']:.1f}°, FLL+Костас RMS={b['phase_rms_deg']:.1f}°")
    print("=== 2.7.9 QPSK «1,1»")
    ordered4 = digital.constellation_calcdist([1, 1j, -1, -1j], [0, 1, 2, 3], 4, 1,
                                              digital.constellation.AMPLITUDE_NORMALIZATION)
    print(" стандарт QPSK без дифф.:", mpsk(4, vec=(1, 1), ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=10e3, fll=True))
    print(" упорядоч. + дифф.:     ", mpsk(4, vec=(1, 1), const=ordered4, diff=True, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=10e3, fll=True))
    print("=== 2.7.10 8PSK «6,6»")
    ordered8 = digital.constellation_calcdist([cmath.exp(1j * math.pi * k / 4) for k in range(8)],
                                              list(range(8)), 8, 1,
                                              digital.constellation.AMPLITUDE_NORMALIZATION)
    print(" стандарт 8PSK без дифф.:", mpsk(8, vec=(6, 6), ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=10e3, fll=True))
    print(" упорядоч. + дифф.:      ", mpsk(8, vec=(6, 6), const=ordered8, diff=True, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, foff_hz=10e3, fll=True))
    print("=== помехоустойчивость QPSK vs 8PSK (случайные данные, шум)")
    for nv in (0.1, 0.2, 0.3):
        a = mpsk(4, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, noise=nv, fll=True)
        b = mpsk(8, ted=digital.TED_GARDNER, resamp=digital.IR_PFB_MF, noise=nv, fll=True)
        print(f"  noise={nv}: QPSK RMS={a['phase_rms_deg']:.1f}° (порог 45°),  8PSK RMS={b['phase_rms_deg']:.1f}° (порог 22.5°)")
