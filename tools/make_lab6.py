# -*- coding: utf-8 -*-
"""Генератор .grc-файлов для лабораторной работы №6 (QAM). Файлы пишутся в папку lab6/.
Запуск:  D:\\radioconda\\python.exe tools\\make_lab6.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_lab5 as base  # класс FG и общие функции
from make_lab5 import FG, qt_range, time_sink, const_sink

OUT6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lab6")
os.makedirs(OUT6, exist_ok=True)

# полоса петли: LB = 4 / (zeta * T * Fвх) = 4 / (0.7071 * 0.005 * 50000) = 0.0226
LOOP_BW = "0.0226"
# девиация частоты 4 кГц в рад/отсчёт на входе приёмника (50 кБод): 2*pi*4000/50000
FDEV = "0.503"


def grid_expr(M):
    """Квадратная решётка QAM с шагом 1 и центром в нуле (как в ЛР: для 16QAM ±0.5, ±1.5)."""
    m = int(round(M ** 0.5))
    h = (m - 1) / 2
    return f"[a+1j*b for a in [x-{h} for x in range({m})] for b in [x-{h} for x in range({m})]]"


def build(fid, title, M, src="random", vector=None, bits=None, tx_table="points", delay=0, sdr=False):
    """src: 'random' | 'vector' (сразу номера символов) | 'packed' (Vector Source + Packed to Unpacked)."""
    fg = FG(fid, title)
    obj = f"QAM{M}"
    fg.var("samp_rate", "2e6", (200, 12))
    fg.var("M", str(M), (300, 12))
    fg.var("symb_rate", "50e3", (380, 12))
    fg.add("variable_rrc_filter_taps", (480, 12), bname="rrc", gain="40", samp_rate="samp_rate",
           sym_rate="symb_rate", alpha="0.4", ntaps="40")
    fg.add("variable_rrc_filter_taps", (660, 12), bname="rrc_1", gain="1", samp_rate="samp_rate",
           sym_rate="symb_rate", alpha="0.4", ntaps="40")
    fg.add("variable_constellation", (840, 12), bname=obj, type="calcdist",
           sym_map="list(range(M))", const_points=grid_expr(M), rot_sym="4", dims="1",
           normalization="digital.constellation.AMPLITUDE_NORMALIZATION", precision="8")

    # ---------------- передатчик
    if src == "random":
        s = fg.add("analog_random_source_x", (8, 180), bname="src", type="byte", min="0", max="M",
                   num_samps="1000", repeat="True")
    else:
        s = fg.add("blocks_vector_source_x", (8, 180), bname="src", type="byte", vector=vector,
                   repeat="True")
    if not sdr:
        thr = fg.add("blocks_throttle2", (8, 290), type="byte", samples_per_second="symb_rate")
        fg.con(s, thr)
        s = thr
    if src == "packed":
        p2u = fg.add("blocks_packed_to_unpacked_xx", (200, 290), bname="p2u", type="byte",
                     bits_per_chunk=str(bits), endianness="gr.GR_MSB_FIRST")
        fg.con(s, p2u)
        s = p2u
    table = grid_expr(M) if tx_table == "grid" else f"{obj}.points()"
    c2s = fg.add("digital_chunks_to_symbols_xx", (400, 180), bname="chunks2sym", in_type="byte",
                 out_type="complex", dimension="1", symbol_table=table)
    fg.con(s, c2s)
    lim = 2.5 if tx_table == "grid" else 2
    cs_tx = const_sink(fg, (400, 300), "Передаваемое", lim=lim)
    fg.con(c2s, cs_tx)
    itp = fg.add("interp_fir_filter_xxx", (650, 180), bname="tx_filter", type="ccc",
                 interp="int(samp_rate/symb_rate)", taps="rrc", samp_delay="0")
    fg.con(c2s, itp)

    if sdr:
        fg.var("center_freq", "433.92e6", (1000, 12))
        qt_range(fg, "tx_gain", "TX gain (HackRF), дБ", 0, 0, 47, 1, (1000, 90))
        qt_range(fg, "rx_gain", "RX gain (RTL-SDR), дБ", 30, 0, 49, 1, (1170, 90))
        qt_range(fg, "ppm", "RX ppm", 0, -100, 100, 1, (1340, 90))
        amp = fg.add("blocks_multiply_const_vxx", (850, 190), type="complex", const="0.3")
        fg.con(itp, amp)
        snk = fg.add("osmosdr_sink", (1000, 170), bname="sdr_tx", args='"numchan=1 hackrf=0"',
                     sample_rate="samp_rate", freq0="center_freq", gain0="tx_gain", if_gain0="20",
                     bb_gain0="20", bw0="0")
        fg.con(amp, snk)
        rx_in = fg.add("osmosdr_source", (8, 520), bname="sdr_rx", args='"numchan=1 rtl=0"',
                       sample_rate="samp_rate", freq0="center_freq", gain0="rx_gain", corr0="ppm",
                       gain_mode0="False", dc_offset_mode0="2", iq_balance_mode0="2")
    else:
        qt_range(fg, "F", "Частотная расстройка, Гц", 0, 0, 200e3, 100, (1000, 90))
        qt_range(fg, "Noise", "СКО шума", 0, 0, 5, 0.01, (1170, 90))
        ch = fg.add("channels_channel_model", (880, 180), bname="channel", noise_voltage="Noise",
                    freq_offset="F/samp_rate", epsilon="1.0", taps="1.0", seed="0")
        fg.con(itp, ch)
        fg.add("virtual_sink", (1120, 210), bname="vsink", stream_id="QAM")
        fg.con(ch, "vsink")
        rx_in = fg.add("virtual_source", (8, 520), bname="vsrc", stream_id="QAM")

    # ---------------- приёмник
    fs = fg.add("qtgui_freq_sink_x", (230, 420), name='"Спектр"', type="complex", fftsize="1024",
                bw="samp_rate", fc="0", grid="True", average="0.2", nconnections="1")
    fg.con(rx_in, fs)
    eye = fg.add("qtgui_eye_sink_x", (230, 650), bname="eye", type="complex", size="1024",
                 samp_per_symbol="int(samp_rate/symb_rate)", srate="samp_rate", autoscale="True",
                 grid="True")
    fg.con(rx_in, eye)
    x = rx_in
    if sdr:
        # у SDR тактовые генераторы передатчика и приёмника разные -> нужна символьная синхронизация
        ss = fg.add("digital_symbol_sync_xx", (450, 520), bname="symsync", type="cc",
                    ted_type="digital.TED_GARDNER", constellation=f"{obj}.base()",
                    sps="int(samp_rate/symb_rate)", ted_gain="1.0", loop_bw="0.045", damping="1.0",
                    max_dev="1.5", osps="1", resamp_type="digital.IR_PFB_MF", nfilters="128",
                    pfb_mf_taps="firdes.root_raised_cosine(128, 128*samp_rate/symb_rate, 1.0, 0.4, 11*128*int(samp_rate/symb_rate))")
        fg.con(x, ss)
        agc = fg.add("analog_agc_xx", (680, 540), type="complex", rate="1e-3", reference="1.0",
                     gain="1.0", max_gain="65536")
        fg.con(ss, agc)
        x = agc
    else:
        if delay:
            dl = fg.add("blocks_delay", (230, 540), bname="delay", type="complex", delay=str(delay),
                        num_ports="1")
            fg.con(x, dl)
            x = dl
        dec = fg.add("fir_filter_xxx", (450, 540), bname="rx_filter", type="ccc",
                     decim="int(samp_rate/symb_rate)", taps="rrc_1", samp_delay="0")
        fg.con(x, dec)
        x = dec
    cr = fg.add("digital_constellation_receiver_cb", (700, 520), bname="receiver", constellation=obj,
                loop_bw=LOOP_BW, fmin="-" + FDEV, fmax=FDEV)
    fg.con(x, cr)
    ts = time_sink(fg, (1000, 420), "Ошибка (error)", n=1024, srate="symb_rate", autoscale="False",
                   ymin=-0.5, ymax=0.5)
    fg.con(cr, ts, 1, 0)
    # блок №10: без него выходы phase/frequency не подключены и схема падает при запуске
    ns = fg.add("blocks_null_sink", (1000, 520), bname="null_sink", type="float", num_inputs="3")
    fg.con(cr, ns, 1, 0)
    fg.con(cr, ns, 2, 1)
    fg.con(cr, ns, 3, 2)
    cs = const_sink(fg, (1000, 600), "После демодулятора созвездия", lim=2)
    fg.con(cr, cs, 4, 0)
    num = fg.add("qtgui_number_sink", (1000, 760), bname="number", type="byte", name='"Принятый символ"',
                 graph_type="qtgui.NUM_GRAPH_HORIZ", min="0", max="M", avg="0", nconnections="1")
    fg.con(cr, num, 0, 0)
    return fg


def save(fg, fname):
    base.OUT = OUT6
    fg.save(fname)


if __name__ == "__main__":
    S = [
        ("lab6_1_16qam.grc", "lab6_1_16qam", "ЛР6 п.1.1-1.8.4  16QAM", dict(M=16)),
        ("lab6_1_8_5_16qam_one_symbol.grc", "lab6_1_8_5_16qam_one", "ЛР6 п.1.8.5-1.8.6  16QAM: один символ",
         dict(M=16, src="packed", vector="(0x55,)", bits=4)),
        ("lab6_1_8_7_16qam_several.grc", "lab6_1_8_7_16qam_several", "ЛР6 п.1.8.7  16QAM: несколько значений",
         dict(M=16, src="packed", vector="(0x12, 0x34, 0xAB)", bits=4)),
        ("lab6_1_8_8_16qam_sdr.grc", "lab6_1_8_8_16qam_sdr", "ЛР6 п.1.8.8  16QAM через SDR",
         dict(M=16, src="vector", vector="tuple(range(M))", sdr=True, tx_table="points")),
        ("lab6_2_1_64qam.grc", "lab6_2_1_64qam", "ЛР6 п.2.1-2.1.2  64QAM",
         dict(M=64, src="vector", vector="tuple(range(M))", tx_table="points")),
        ("lab6_2_1_3_16qam.grc", "lab6_2_1_3_16qam", "ЛР6 п.2.1.3  меньшая разрядность: 16QAM",
         dict(M=16, src="vector", vector="tuple(range(M))", tx_table="points")),
        ("lab6_2_1_4_64qam_several.grc", "lab6_2_1_4_64qam_several", "ЛР6 п.2.1.4  64QAM: несколько значений",
         dict(M=64, src="vector", vector="(5, 27, 42, 63)", tx_table="points")),
        ("lab6_2_1_5_64qam_sdr.grc", "lab6_2_1_5_64qam_sdr", "ЛР6 п.2.1.5  64QAM через SDR",
         dict(M=64, src="vector", vector="tuple(range(M))", sdr=True, tx_table="points")),
        ("lab6_3_1_256qam.grc", "lab6_3_1_256qam", "ЛР6 п.3.1  256QAM",
         dict(M=256, src="vector", vector="tuple(range(M))", tx_table="points", delay=3)),
        ("lab6_3_2_256qam_sdr.grc", "lab6_3_2_256qam_sdr", "ЛР6 п.3.2  256QAM через SDR",
         dict(M=256, src="vector", vector="tuple(range(M))", sdr=True, tx_table="points")),
    ]
    for fname, fid, title, kw in S:
        save(build(fid, title, **kw), fname)
