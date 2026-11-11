# -*- coding: utf-8 -*-
"""Генератор .grc-файлов для лабораторной работы №5 (GNU Radio 3.10).

Каждая функция fg_* описывает одну схему (один пункт или группу пунктов).
Параметры, которые не заданы явно, берутся из описаний блоков (*.block.yml),
поэтому файлы получаются полными и открываются в GNU Radio Companion без ошибок.
Запуск:  D:\\radioconda\\python.exe tools\\make_lab5.py
"""
import os
import sys
import yaml

GRC_BLOCKS = r"D:/radioconda/Library/share/gnuradio/grc/blocks"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

_cache = {}


def _defaults(block_id):
    """Параметры блока по умолчанию из его .block.yml."""
    if block_id in ("variable", "virtual_sink", "virtual_source", "import"):
        return {}
    if block_id not in _cache:
        path = os.path.join(GRC_BLOCKS, block_id + ".block.yml")
        if not os.path.exists(path):
            # некоторые блоки лежат в файле с другим именем
            for f in os.listdir(GRC_BLOCKS):
                if f.endswith(".block.yml"):
                    with open(os.path.join(GRC_BLOCKS, f), encoding="utf-8") as fh:
                        head = fh.readline()
                    if head.strip() == "id: " + block_id:
                        path = os.path.join(GRC_BLOCKS, f)
                        break
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        res = {}
        for p in d.get("parameters", []):
            # параметры без явного значения по умолчанию (в т.ч. base_key)
            # не записываем – GRC подставит их сам при открытии файла
            if p.get("default") is not None and "base_key" not in p:
                res[p["id"]] = str(p["default"])
        _cache[block_id] = res
    return dict(_cache[block_id])


class FG:
    def __init__(self, fid, title, comment=""):
        self.fid, self.title, self.comment = fid, title, comment
        self.blocks, self.conns = [], []
        self._n = {}

    def add(self, block_id, xy, bname=None, comment="", state="enabled", **params):
        name = bname
        if name is None:
            k = self._n.get(block_id, 0)
            self._n[block_id] = k + 1
            name = f"{block_id}_{k}"
        p = _defaults(block_id)
        if block_id not in ("variable", "import", "virtual_sink", "virtual_source"):
            p.setdefault("affinity", "")
            p.setdefault("alias", "")
            p.setdefault("maxoutbuf", "0")
            p.setdefault("minoutbuf", "0")
        p["comment"] = ""  # надписи под блоками не нужны
        for k, v in params.items():
            p[k] = str(v)
        self.blocks.append({"name": name, "id": block_id, "parameters": p,
                            "states": {"coordinate": list(xy), "rotation": 0, "state": state}})
        return name

    def var(self, name, value, xy, comment=""):
        return self.add("variable", xy, bname=name, comment=comment, value=value)

    def con(self, a, b, pa=0, pb=0):
        self.conns.append([a, str(pa), b, str(pb)])

    def save(self, fname):
        options = {
            "parameters": {
                "author": "Lab5", "catch_exceptions": "True", "category": "[GRC Hier Blocks]",
                "cmake_opt": "", "comment": "", "copyright": "", "description": "",
                "gen_cmake": "On", "gen_linking": "dynamic", "generate_options": "qt_gui",
                "hier_block_src_path": ".:", "id": self.fid, "max_nouts": "0",
                "output_language": "python", "placement": "(0,0)", "qt_qss_theme": "",
                "realtime_scheduling": "", "run": "True", "run_command": "{python} -u {filename}",
                "run_options": "prompt", "sizing_mode": "fixed", "thread_safe_setters": "",
                "title": self.title, "window_size": "(1000,1000)",
            },
            "states": {"bus_sink": False, "bus_source": False, "bus_structure": None,
                       "coordinate": [8, 8], "rotation": 0, "state": "enabled"},
        }
        doc = {"options": options, "blocks": self.blocks, "connections": self.conns,
               "metadata": {"file_format": 1, "grc_version": "3.10.12.0"}}
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, default_flow_style=None, width=200)
        print("written", fname)


# ---------------------------------------------------------------- общие кусочки
def qt_range(fg, name, label, value, start, stop, step, xy, comment=""):
    return fg.add("variable_qtgui_range", xy, bname=name, comment=comment, label=f'"{label}"',
                  value=value, start=start, stop=stop, step=step, rangeType="float")


def time_sink(fg, xy, title, typ="float", n=100, srate="samp_rate", nconn=1, autoscale="True",
              ymin=-1, ymax=4, comment="", **kw):
    return fg.add("qtgui_time_sink_x", xy, comment=comment, name=f'"{title}"', type=typ, size=n,
                  srate=srate, nconnections=nconn, autoscale=autoscale, ymin=ymin, ymax=ymax,
                  grid="True", **kw)


def const_sink(fg, xy, title, nconn=1, n=1024, autoscale="False", lim=2, comment=""):
    return fg.add("qtgui_const_sink_x", xy, comment=comment, name=f'"{title}"', size=n,
                  nconnections=nconn, autoscale=autoscale, grid="True",
                  xmin=-lim, xmax=lim, ymin=-lim, ymax=lim)


DQPSK_TABLE = "[0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j]"


# =========================================================== ЧАСТЬ 1. DQPSK
def fg_dqpsk(variant):
    """variant: 'base' (1.1-1.9.2), 'phase' (1.9.3), 'one' (1.9.4), 'sdr' (1.9.5)"""
    titles = {
        "base": "ЛР5 п.1.1-1.9.2  DQPSK: передача и приём",
        "phase": "ЛР5 п.1.9.3  DQPSK: вывод фазового приращения",
        "one": "ЛР5 п.1.9.4  DQPSK: передача одного символа",
        "sdr": "ЛР5 п.1.9.5  DQPSK через SDR (HackRF -> RTL-SDR)",
        "het": "ЛР5 п.1.9.1  DQPSK: компенсация расстройки гетеродином",
    }
    fid = {"base": "lab5_1_dqpsk", "phase": "lab5_1_9_3_dqpsk_phase",
           "one": "lab5_1_9_4_dqpsk_one_symbol", "sdr": "lab5_1_9_5_dqpsk_sdr",
           "het": "lab5_1_9_1_dqpsk_heterodyne"}[variant]
    fg = FG(fid, titles[variant])
    fg.var("samp_rate", "2e6", (200, 12))
    vec = "(2,)" if variant in ("one",) else "(0, 1, 2, 3)"
    vcom = ("п.1.9.4: передаётся один символ «2»" if variant == "one"
            else "п.1.2: весь алфавит DQPSK – символы 0,1,2,3")
    v = fg.add("blocks_vector_source_x", (8, 180), bname="src", comment=vcom, type="byte",
               vector=vec, repeat="True")
    if variant == "sdr":
        fg.var("sps", "10", (300, 12), comment="отсчётов на символ (Rs = 200 кБод)")
        fg.var("center_freq", "433.92e6", (390, 12), comment="несущая, ISM 433 МГц")
        src_out = v
    else:
        thr = fg.add("blocks_throttle2", (8, 300), type="byte", samples_per_second="samp_rate",
                     comment="ограничение скорости в симуляции (без SDR)")
        fg.con(v, thr)
        src_out = thr
    u2f = fg.add("blocks_uchar_to_float", (300, 100))
    fg.con(src_out, u2f)
    tx_ts = time_sink(fg, (500, 60), "Переданное", n=100)
    fg.con(u2f, tx_ts)
    enc = fg.add("digital_diff_encoder_bb", (250, 260), bname="diff_enc", modulus=4,
                 coding="digital.DIFF_DIFFERENTIAL", comment="п.1.3: модуль = M = 4")
    fg.con(src_out, enc)
    c2s = fg.add("digital_chunks_to_symbols_xx", (470, 250), bname="chunks2sym",
                 in_type="byte", out_type="complex", dimension=1, symbol_table=DQPSK_TABLE,
                 comment="п.1.4: точки QPSK на углах 45°,135°,225°,315°")
    fg.con(enc, c2s)

    if variant != "sdr":
        qt_range(fg, "n", "Noise Voltage, мВ", 0, 0, 1000, 1, (150, 470),
                 comment="п.1.5 / 1.9.2: СКО шума в мВ")
        qt_range(fg, "f", "Расстройка частоты, Гц", 0, -10e3, 10e3, 10, (320, 470),
                 comment="п.1.5 / 1.9.1: абсолютная расстройка в Гц")
        ch = fg.add("channels_channel_model", (720, 220), bname="channel",
                    noise_voltage="n*1e-3", freq_offset="f/samp_rate", epsilon="1.0",
                    taps="1.0", seed="0",
                    comment="п.1.5: Frequency Offset – относительный: f/samp_rate")
        fg.con(c2s, ch)
        fg.add("virtual_sink", (960, 250), bname="vsink", stream_id="dqpsk")
        fg.con(ch, "vsink")
        rx_in = fg.add("virtual_source", (8, 640), bname="vsrc", stream_id="dqpsk")
        if variant == "het":
            # гетеродин: exp(-j*2*pi*f*t) переносит спектр обратно на нулевую частоту
            lo = fg.add("analog_sig_source_x", (8, 760), bname="heterodyne", type="complex",
                        samp_rate="samp_rate", waveform="analog.GR_COS_WAVE", freq="-f",
                        amp="1", offset="0", phase="0")
            mix = fg.add("blocks_multiply_xx", (200, 720), bname="mixer", type="complex",
                         num_inputs="2")
            fg.con(rx_in, mix, 0, 0)
            fg.con(lo, mix, 0, 1)
            rx_in = mix
    else:
        qt_range(fg, "tx_gain", "TX gain (HackRF), дБ", 0, 0, 47, 1, (150, 470))
        qt_range(fg, "rx_gain", "RX gain (RTL-SDR), дБ", 30, 0, 49, 1, (320, 470))
        qt_range(fg, "ppm", "RX ppm", 0, -100, 100, 1, (490, 470))
        rep = fg.add("blocks_repeat", (690, 250), type="complex", interp="sps",
                     comment="каждый символ повторяется sps раз (прямоугольный импульс)")
        fg.con(c2s, rep)
        amp = fg.add("blocks_multiply_const_vxx", (850, 250), type="complex", const="0.5",
                     comment="запас по амплитуде для ЦАП")
        fg.con(rep, amp)
        snk = fg.add("osmosdr_sink", (1010, 200), bname="sdr_tx",
                     args='"numchan=1 hackrf=0"', sample_rate="samp_rate", freq0="center_freq",
                     gain0="tx_gain", if_gain0="20", bb_gain0="20", bw0="0",
                     comment="Передатчик HackRF (замените hackrf=0 на своё устройство)")
        fg.con(amp, snk)
        rx = fg.add("osmosdr_source", (8, 600), bname="sdr_rx", args='"numchan=1 rtl=0"',
                    sample_rate="samp_rate", freq0="center_freq", gain0="rx_gain",
                    corr0="ppm", gain_mode0="False", dc_offset_mode0="2", iq_balance_mode0="2",
                    comment="Приёмник RTL-SDR")
        agc = fg.add("analog_agc_xx", (230, 620), type="complex", rate="1e-4", reference="1.0",
                     gain="1.0", max_gain="65536", comment="выравнивание амплитуды")
        fg.con(rx, agc)
        ss = fg.add("digital_symbol_sync_xx", (400, 600), bname="symsync", type="cc",
                    ted_type="digital.TED_GARDNER", sps="sps", ted_gain="1.0", loop_bw="0.045",
                    damping="1.0", max_dev="1.5", osps="1", resamp_type="digital.IR_MMSE_8TAP",
                    comment="символьная синхронизация: 1 отсчёт на символ")
        fg.con(agc, ss)
        fsk = fg.add("qtgui_freq_sink_x", (230, 800), name='"Спектр принятого"', type="complex",
                     fftsize="2048", bw="samp_rate", fc="center_freq", grid="True",
                     average="0.2", nconnections="1")
        fg.con(rx, fsk)
        rx_in = ss

    dph = fg.add("digital_diff_phasor_cc", (720 if variant == "sdr" else 200, 660), bname="diffphasor",
                 comment="п.1.7: y[n] = x[n]·conj(x[n-1]) – приращение фазы")
    fg.con(rx_in, dph)
    cs = const_sink(fg, (900, 760), "Созвездие: до (1) / после Differential Phasor (2)", nconn=2,
                    autoscale="False", lim=1.5)
    fg.con(rx_in, cs, 0, 0)
    fg.con(dph, cs, 0, 1)
    fg.add("variable_constellation", (950, 420), bname="dqpsk", type="calcdist",
           sym_map="[0, 1, 2, 3]", const_points="[1, 1j, -1, -1j]", rot_sym="4", dims="1",
           normalization="digital.constellation.AMPLITUDE_NORMALIZATION", precision="8",
           comment="п.1.8: точки = приращения фазы 0°,90°,180°,270°")
    dec = fg.add("digital_constellation_decoder_cb", (450, 600), bname="decoder",
                 constellation="dqpsk")
    fg.con(dph, dec)
    u2f2 = fg.add("blocks_uchar_to_float", (660, 600))
    fg.con(dec, u2f2)
    rx_ts = time_sink(fg, (850, 560), "Принятое", n=100)
    fg.con(u2f2, rx_ts)

    if variant == "phase":
        arg = fg.add("blocks_complex_to_arg", (450, 760), bname="c2arg",
                     comment="п.1.9.3: фаза комплексного отсчёта, рад")
        fg.con(dph, arg)
        deg = fg.add("blocks_multiply_const_vxx", (620, 760), bname="rad2deg", type="float",
                     const="57.2958", comment="перевод в градусы")
        fg.con(arg, deg)
        ph_ts = time_sink(fg, (850, 880), "Фазовое приращение, град", n=100, autoscale="False",
                          ymin=-200, ymax=200)
        fg.con(deg, ph_ts)
    return fg


def fg_dqpsk_fll():
    """п.1.9.1: DQPSK с RRC-фильтром; сравнение приёма без FLL и с FLL Band-Edge."""
    fg = FG("lab5_1_9_1_dqpsk_fll", "ЛР5 п.1.9.1  DQPSK: без АПЧ / с FLL Band-Edge")
    fg.var("samp_rate", "2e6", (200, 12))
    fg.var("sps", "10", (300, 12))
    fg.var("alpha", "0.35", (390, 12))
    fg.var("Rs", "samp_rate/sps", (480, 12))
    fg.add("variable_constellation", (950, 12), bname="dqpsk", type="calcdist",
           sym_map="[0, 1, 2, 3]", const_points="[1, 1j, -1, -1j]", rot_sym="4", dims="1",
           normalization="digital.constellation.AMPLITUDE_NORMALIZATION", precision="8")
    qt_range(fg, "n", "Noise Voltage, мВ", 0, 0, 1000, 1, (680, 12))
    qt_range(fg, "f", "Расстройка частоты, Гц", 0, -50e3, 50e3, 100, (800, 90))
    src = fg.add("analog_random_uniform_source_x", (8, 160), bname="src", type="byte",
                 minimum="0", maximum="4", seed="0")
    thr = fg.add("blocks_throttle2", (8, 280), type="byte", samples_per_second="Rs")
    fg.con(src, thr)
    enc = fg.add("digital_diff_encoder_bb", (200, 280), bname="diff_enc", modulus=4,
                 coding="digital.DIFF_DIFFERENTIAL")
    fg.con(thr, enc)
    c2s = fg.add("digital_chunks_to_symbols_xx", (400, 270), bname="chunks2sym", in_type="byte",
                 out_type="complex", dimension=1, symbol_table=DQPSK_TABLE)
    fg.con(enc, c2s)
    rrc = fg.add("interp_fir_filter_xxx", (620, 270), bname="rrc_tx", type="ccf",
                 interp="sps", taps="firdes.root_raised_cosine(sps, sps, 1.0, alpha, 11*sps)",
                 samp_delay="0")
    fg.con(c2s, rrc)
    ch = fg.add("channels_channel_model", (820, 230), bname="channel", noise_voltage="n*1e-3",
                freq_offset="f/samp_rate", epsilon="1.0", taps="1.0", seed="0")
    fg.con(rrc, ch)
    fg.add("virtual_sink", (1060, 260), bname="vsink", stream_id="dqpsk")
    fg.con(ch, "vsink")
    tu = fg.add("blocks_uchar_to_float", (200, 160))
    fg.con(thr, tu)
    tts = time_sink(fg, (380, 120), "Переданное", n=100, srate="Rs", autoscale="False", ymin=-1, ymax=4)
    fg.con(tu, tts)

    vs = fg.add("virtual_source", (8, 480), bname="vsrc", stream_id="dqpsk")
    fll = fg.add("digital_fll_band_edge_cc", (200, 600), bname="fll", type="cc",
                 samps_per_sym="sps", rolloff="alpha", filter_size="44", w="0.00628")
    fg.con(vs, fll)
    spec = fg.add("qtgui_freq_sink_x", (200, 380), name='"Спектр: до FLL / после FLL"',
                  type="complex", fftsize="4096", bw="samp_rate", fc="0", grid="True",
                  average="0.1", nconnections="2", ymin="-100", ymax="10")
    fg.con(vs, spec, 0, 0)
    fg.con(fll, spec, 0, 1)
    taps = "firdes.root_raised_cosine(128, 128*sps, 1.0, alpha, 11*sps*128)"
    cs = const_sink(fg, (1100, 520), "После Differential Phasor: без FLL / с FLL", nconn=2, lim=1.5)
    ts = time_sink(fg, (1100, 700), "Принятое: без FLL / с FLL", n=100, srate="Rs", nconn=2,
                   autoscale="False", ymin=-1, ymax=4)
    for k, (inp, y) in enumerate(((vs, 480), (fll, 620))):
        tag = ("a", "b")[k]
        ss = fg.add("digital_symbol_sync_xx", (430, y), bname="symsync_" + tag, type="cc",
                    ted_type="digital.TED_GARDNER", constellation="digital.constellation_qpsk().base()",
                    sps="sps", ted_gain="1.0", loop_bw="0.045", damping="1.0", max_dev="1.5",
                    osps="1", resamp_type="digital.IR_PFB_MF", nfilters="128", pfb_mf_taps=taps)
        fg.con(inp, ss)
        dp = fg.add("digital_diff_phasor_cc", (720, y + 20), bname="diffphasor_" + tag)
        fg.con(ss, dp)
        fg.con(dp, cs, 0, k)
        dec = fg.add("digital_constellation_decoder_cb", (880, y + 60), bname="decoder_" + tag,
                     constellation="dqpsk")
        fg.con(dp, dec)
        u = fg.add("blocks_uchar_to_float", (1000, y + 100))
        fg.con(dec, u)
        fg.con(u, ts, 0, k)
    return fg


def fg_dqpsk_fll_simple():
    """п.1.9.1 (упрощённая): Vector Source, без Symbol Sync – RRC + Delay + Keep One in N."""
    fg = FG("lab5_1_9_1_dqpsk_fll_simple", "ЛР5 п.1.9.1  DQPSK: без АПЧ / с FLL (упрощённая)")
    fg.var("samp_rate", "2e6", (200, 12))
    fg.var("sps", "10", (300, 12))
    fg.var("alpha", "0.35", (390, 12))
    fg.var("Rs", "samp_rate/sps", (480, 12))
    fg.add("variable_constellation", (950, 12), bname="dqpsk", type="calcdist",
           sym_map="[0, 1, 2, 3]", const_points="[1, 1j, -1, -1j]", rot_sym="4", dims="1",
           normalization="digital.constellation.AMPLITUDE_NORMALIZATION", precision="8")
    qt_range(fg, "n", "Noise Voltage, мВ", 0, 0, 1000, 1, (680, 12))
    qt_range(fg, "f", "Расстройка частоты, Гц", 0, -50e3, 50e3, 100, (800, 90))
    src = fg.add("blocks_vector_source_x", (8, 160), bname="src", type="byte",
                 vector="(0, 1, 2, 3)", repeat="True")
    thr = fg.add("blocks_throttle2", (8, 280), type="byte", samples_per_second="Rs")
    fg.con(src, thr)
    enc = fg.add("digital_diff_encoder_bb", (200, 280), bname="diff_enc", modulus=4,
                 coding="digital.DIFF_DIFFERENTIAL")
    fg.con(thr, enc)
    c2s = fg.add("digital_chunks_to_symbols_xx", (400, 270), bname="chunks2sym", in_type="byte",
                 out_type="complex", dimension=1, symbol_table=DQPSK_TABLE)
    fg.con(enc, c2s)
    rrc = fg.add("interp_fir_filter_xxx", (620, 270), bname="rrc_tx", type="ccf",
                 interp="sps", taps="firdes.root_raised_cosine(sps, sps, 1.0, alpha, 111)", samp_delay="0")
    fg.con(c2s, rrc)
    ch = fg.add("channels_channel_model", (820, 230), bname="channel", noise_voltage="n*1e-3",
                freq_offset="f/samp_rate", epsilon="1.0", taps="1.0", seed="0")
    fg.con(rrc, ch)
    fg.add("virtual_sink", (1060, 260), bname="vsink", stream_id="dqpsk")
    fg.con(ch, "vsink")
    tu = fg.add("blocks_uchar_to_float", (200, 160))
    fg.con(thr, tu)
    tts = time_sink(fg, (380, 120), "Переданное", n=100, srate="Rs", autoscale="False", ymin=-1, ymax=4)
    fg.con(tu, tts)

    vs = fg.add("virtual_source", (8, 480), bname="vsrc", stream_id="dqpsk")
    fll = fg.add("digital_fll_band_edge_cc", (200, 600), bname="fll", type="cc",
                 samps_per_sym="sps", rolloff="alpha", filter_size="44", w="0.00628")
    fg.con(vs, fll)
    spec = fg.add("qtgui_freq_sink_x", (200, 380), name='"Спектр: до FLL / после FLL"',
                  type="complex", fftsize="4096", bw="samp_rate", fc="0", grid="True",
                  average="0.1", nconnections="2", ymin="-100", ymax="10")
    fg.con(vs, spec, 0, 0)
    fg.con(fll, spec, 0, 1)
    cs = const_sink(fg, (1250, 520), "После Differential Phasor: без FLL / с FLL", nconn=2, lim=1.5)
    ts = time_sink(fg, (1250, 700), "Принятое: без FLL / с FLL", n=100, srate="Rs", nconn=2,
                   autoscale="False", ymin=-1, ymax=4)
    for k, (inp, y) in enumerate(((vs, 480), (fll, 620))):
        tag = ("a", "b")[k]
        mf = fg.add("fir_filter_xxx", (380, y), bname="rrc_rx_" + tag, type="ccf", decim="1",
                    taps="firdes.root_raised_cosine(1, sps, 1.0, alpha, 111)", samp_delay="0")
        fg.con(inp, mf)
        dl = fg.add("blocks_delay", (560, y), bname="delay_" + tag, type="complex", delay=("2", "8")[k],
                    num_ports="1")
        fg.con(mf, dl)
        k1 = fg.add("blocks_keep_one_in_n", (720, y), bname="keep_" + tag, type="complex", n="sps")
        fg.con(dl, k1)
        dp = fg.add("digital_diff_phasor_cc", (900, y + 20), bname="diffphasor_" + tag)
        fg.con(k1, dp)
        fg.con(dp, cs, 0, k)
        dec = fg.add("digital_constellation_decoder_cb", (1050, y + 60), bname="decoder_" + tag,
                     constellation="dqpsk")
        fg.con(dp, dec)
        u = fg.add("blocks_uchar_to_float", (1150, y + 100))
        fg.con(dec, u)
        fg.con(u, ts, 0, k)
    return fg


# =========================================================== ЧАСТЬ 2. M-PSK
def fg_mpsk(p):
    """p – словарь настроек варианта схемы части 2."""
    fg = FG(p["id"], p["title"])
    M = p.get("M", 2)
    fg.var("samp_rate", "2e6", (200, 12))
    fg.var("sps", str(p.get("sps", 10)), (300, 12))
    fg.var("alpha", "0.4", (390, 12), comment="коэффициент скругления RRC")
    fg.var("Rs", "samp_rate/sps", (480, 12), comment="символьная скорость = 200 кБод")
    ctype = {2: "bpsk", 4: "qpsk", 8: "8psk"}[M]
    if p.get("const") == "ordered":
        # точки упорядочены по углу -> дифференциальное кодирование корректно
        # точки повёрнуты на pi/M: именно в таком положении петля Костаса M-го порядка
        # захватывает созвездие (иначе решения попадают на границы областей)
        pts = {4: "[0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j]",
               8: "[0.924+0.383j, 0.383+0.924j, -0.383+0.924j, -0.924+0.383j, "
                  "-0.924-0.383j, -0.383-0.924j, 0.383-0.924j, 0.924-0.383j]"}[M]
        fg.add("variable_constellation", (700, 12), bname="psk", type="calcdist",
               const_points=pts, sym_map=str(list(range(M))), rot_sym=str(M), dims="1",
               normalization="digital.constellation.AMPLITUDE_NORMALIZATION", precision="8",
               comment=f"{M}PSK: точки по кругу по порядку 0..{M-1} (для дифф. кодирования)")
    else:
        fg.add("variable_constellation", (700, 12), bname="psk", type=ctype, precision="8",
               comment={2: "п.2.1: BPSK", 4: "п.2.7.6: QPSK", 8: "8PSK"}[M])
    if p.get("N_var"):
        fg.var("N", "1", (900, 12), comment="п.2.7.7: номер по списку")

    # ---------------- передатчик
    if p.get("packed"):
        # готовые байты: биты всех символов подряд, модулятор сам режет их на символы
        src = fg.add("blocks_vector_source_x", (8, 160), bname="src", type="byte",
                     vector=p["packed"], repeat="True")
        bpc = None
    elif p.get("vector"):
        src = fg.add("blocks_vector_source_x", (8, 160), bname="src", type="byte",
                     vector=p["vector"], repeat="True", comment=p.get("vector_comment", ""))
        bpc = {2: 1, 4: 2, 8: 3}[M]
    else:
        src = fg.add("analog_random_uniform_source_x", (8, 160), bname="src", type="byte",
                     minimum="0", maximum="2", seed="0", comment="п.2.2: случайные биты 0/1")
        bpc = 1
    if bpc is None:
        pack = src
    else:
        pack = fg.add("blocks_unpacked_to_packed_xx", (200, 260), bname="pack", type="byte",
                      bits_per_chunk=str(bpc), endianness="gr.GR_MSB_FIRST",
                      comment="упаковка в байты (модулятор сам режет их на символы)")
        fg.con(src, pack)
    mod = fg.add("digital_constellation_modulator", (400, 150), bname="mod", constellation="psk",
                 differential=p.get("diff", "False"), samples_per_symbol="sps", excess_bw="alpha",
                 verbose="False", log="False", truncate="False",
                 comment="п.2.3: модуляция + RRC-фильтр")
    fg.con(pack, mod)
    if p.get("sdr"):
        fg.var("center_freq", "433.92e6", (1000, 12))
        qt_range(fg, "tx_gain", "TX gain (HackRF), дБ", 0, 0, 47, 1, (1000, 80))
        qt_range(fg, "rx_gain", "RX gain (RTL-SDR), дБ", 30, 0, 49, 1, (1170, 80))
        qt_range(fg, "ppm", "RX ppm", 0, -100, 100, 1, (1340, 80))
        amp = fg.add("blocks_multiply_const_vxx", (650, 170), type="complex", const="0.5")
        fg.con(mod, amp)
        snk = fg.add("osmosdr_sink", (830, 140), bname="sdr_tx", args='"numchan=1 hackrf=0"',
                     sample_rate="samp_rate", freq0="center_freq", gain0="tx_gain", if_gain0="20",
                     bb_gain0="20", bw0="0", comment="Передатчик HackRF")
        fg.con(amp, snk)
        tx_out = fg.add("osmosdr_source", (8, 520), bname="sdr_rx", args='"numchan=1 rtl=0"',
                        sample_rate="samp_rate", freq0="center_freq", gain0="rx_gain", corr0="ppm",
                        gain_mode0="False", dc_offset_mode0="2", iq_balance_mode0="2",
                        comment="Приёмник RTL-SDR")
        agc = fg.add("analog_agc_xx", (8, 640), type="complex", rate="1e-4", reference="1.0",
                     gain="1.0", max_gain="65536")
        fg.con(tx_out, agc)
        rx_in = agc
        spec_src = tx_out
    else:
        thr = fg.add("blocks_throttle2", (650, 170), type="complex", samples_per_second="samp_rate")
        fg.con(mod, thr)
        qt_range(fg, "noise", "Noise Voltage, В", p.get("noise", 0), 0, 1, 0.001, (1000, 80),
                 comment="СКО шума канала")
        foff = p.get("foff", "0")
        ch = fg.add("channels_channel_model", (820, 140), bname="channel", noise_voltage="noise",
                    freq_offset=foff, epsilon="1.0", taps="1.0", seed="0",
                    comment=p.get("ch_comment", "п.2.3: канал с шумом"))
        fg.con(thr, ch)
        fg.add("virtual_sink", (1080, 300), bname="vsink", stream_id="psk")
        fg.con(ch, "vsink")
        spec_src = ch
        rx_in = fg.add("virtual_source", (8, 560), bname="vsrc", stream_id="psk")
    fs = fg.add("qtgui_freq_sink_x", (1080, 140), name='"Спектр переданного сигнала"',
                type="complex", fftsize="8192", bw="samp_rate", fc="0", grid="True",
                average="0.1", nconnections="1", comment="п.2.7: ширина спектра = Rs(1+alpha)")
    fg.con(spec_src, fs)
    ts = time_sink(fg, (1080, 30), "Временное представление сигнала", typ="complex", n=1024,
                   autoscale="False", ymin=-1.5, ymax=1.5)
    fg.con(spec_src, ts)

    # ---------------- приёмник
    cs0 = const_sink(fg, (250, 470), "Созвездие принятого сигнала", lim=2)
    fg.con(rx_in, cs0)
    chain_in = rx_in
    if p.get("fll"):
        fll = fg.add("digital_fll_band_edge_cc", (230, 560), bname="fll", type="cc",
                     samps_per_sym="sps", rolloff="alpha", filter_size="44", w="0.00628",
                     comment="п.2.7.7: FLL по краям полосы; полоса петли 2pi/1000 (2pi/100 даёт сильный джиттер)")
        fg.con(chain_in, fll)
        chain_in = fll
    osps = p.get("osps", "1")
    ss = fg.add("digital_symbol_sync_xx", (450, 600), bname="symsync", type="cc",
                ted_type=p.get("ted", "digital.TED_EARLY_LATE"), constellation="psk",
                sps="sps", ted_gain="1.0", loop_bw=p.get("ss_bw", "alpha"), damping="1", max_dev="1.5",
                osps=osps, resamp_type=p.get("resamp", "digital.IR_MMSE_8TAP"),
                nfilters="128",
                pfb_mf_taps="firdes.root_raised_cosine(128, 128*sps, 1.0, alpha, 11*sps*128)",
                comment=p.get("ss_comment", "п.2.5: символьная синхронизация"))
    fg.con(chain_in, ss)
    eye_sps = p.get("eye_sps", "sps")
    eye = fg.add("qtgui_eye_sink_x", (750, 470), bname="eye", type="complex", size="2048",
                 samp_per_symbol=eye_sps, srate=p.get("eye_srate", "samp_rate"),
                 autoscale="True", grid="True", ymin="-2", ymax="2",
                 comment=p.get("eye_comment", "глазковая диаграмма после Symbol Sync"))
    fg.con(ss, eye)
    if p.get("sync") == "coarse":
        mul = fg.add("blocks_multiply_xx", (750, 680), bname="square", type="complex",
                     num_inputs="2", comment="п.2.6: x² – снимает BPSK-модуляцию")
        fg.con(ss, mul, 0, 0)
        fg.con(ss, mul, 0, 1)
        pll = fg.add("analog_pll_carriertracking_cc", (930, 670), bname="pll", w="0.0628",
                     max_freq="0.7", min_freq="-0.7",
                     comment="п.2.6: ФАПЧ по несущей (грубая)")
        fg.con(mul, pll)
        out = pll
    else:
        cos = fg.add("digital_costas_loop_cc", (750, 680), bname="costas", w=p.get("costas_w", "0.0628"),
                     order=str(M), use_snr="False",
                     comment=p.get("costas_comment", "п.2.7.2: петля Костаса (точная)"))
        fg.con(ss, cos)
        out = cos
    cs1 = const_sink(fg, (1100, 650), "Созвездие синхронизированного сигнала", lim=2)
    fg.con(out, cs1)

    if p.get("decode"):
        dec = fg.add("digital_constellation_decoder_cb", (930, 820), bname="decoder",
                     constellation="psk")
        fg.con(out, dec)
        last = dec
        if p.get("diff") == "True":
            dd = fg.add("digital_diff_decoder_bb", (1100, 820), bname="diff_dec", modulus=str(M),
                        coding="digital.DIFF_DIFFERENTIAL",
                        comment="снятие неоднозначности фазы петли Костаса")
            fg.con(dec, dd)
            last = dd
        u2f = fg.add("blocks_uchar_to_float", (1260, 830))
        fg.con(last, u2f)
        rts = time_sink(fg, (1260, 900), "Принятые символы", n=100, srate="Rs",
                        autoscale="False", ymin=-1, ymax=M)
        fg.con(u2f, rts)
        tu = fg.add("blocks_uchar_to_float", (200, 380))
        if bpc is None:
            # для наглядности режем байты на символы так же, как это делает модулятор
            p2u = fg.add("blocks_packed_to_unpacked_xx", (8, 380), bname="p2u", type="byte",
                         bits_per_chunk={2: "1", 4: "2", 8: "3"}[M], endianness="gr.GR_MSB_FIRST")
            fg.con(src, p2u)
            fg.con(p2u, tu)
        else:
            fg.con(src, tu)
        tts = time_sink(fg, (380, 380), "Переданные символы", n=100, srate="Rs",
                        autoscale="False", ymin=-1, ymax=M)
        fg.con(tu, tts)
    return fg


PART2 = [
    dict(fname="lab5_2_1_bpsk.grc", id="lab5_2_1_bpsk",
         title="ЛР5 п.2.1-2.7.1  BPSK: Symbol Sync + грубая синхронизация (x² + PLL)",
         sync="coarse"),
    dict(fname="lab5_2_7_2_bpsk_costas.grc", id="lab5_2_7_2_bpsk_costas",
         title="ЛР5 п.2.7.2  BPSK: точная синхронизация – петля Костаса"),
    dict(fname="lab5_2_7_3_bpsk_ted.grc", id="lab5_2_7_3_bpsk_ted",
         title="ЛР5 п.2.7.3  BPSK: шум 50 мВ, выбранный TED – Gardner", noise=0.05,
         ted="digital.TED_GARDNER",
         ss_comment="п.2.7.3: сравнивались все TED, оставлен Gardner"),
    dict(fname="lab5_2_7_4_bpsk_osps.grc", id="lab5_2_7_4_bpsk_osps",
         title="ЛР5 п.2.7.4  BPSK: Output Samples/Symbol = sps", ted="digital.TED_GARDNER",
         osps="sps", ss_comment="п.2.7.4: на выходе sps отсчётов на символ",
         eye_comment="глаз раскрыт на 1/Rs = 5 мкс"),
    dict(fname="lab5_2_7_5_bpsk_resampler.grc", id="lab5_2_7_5_bpsk_resampler",
         title="ЛР5 п.2.7.5  BPSK: выбор интерполятора (PFB + согласованный фильтр)",
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF",
         ss_comment="п.2.7.5: Polyphase Filterbank, MF – интерполятор + согласованный RRC"),
    dict(fname="lab5_2_7_6_qpsk.grc", id="lab5_2_7_6_qpsk",
         title="ЛР5 п.2.7.6  QPSK", M=4, ss_bw="0.045", ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF",
         costas_comment="петля Костаса 4-го порядка"),
    dict(fname="lab5_2_7_7a_qpsk_foffset_costas.grc", id="lab5_2_7_7a_qpsk_foffset",
         title="ЛР5 п.2.7.7(а)  QPSK: расстройка N·10 кГц, только Костас", M=4, ss_bw="0.045", N_var=True,
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF",
         foff="N*10e3/samp_rate", ch_comment="п.2.7.7: расстройка N·10 кГц (относительная)"),
    dict(fname="lab5_2_7_7b_qpsk_fll.grc", id="lab5_2_7_7b_qpsk_fll",
         title="ЛР5 п.2.7.7(б)  QPSK: FLL Band-Edge + Symbol Sync + Костас", M=4, ss_bw="0.045", N_var=True,
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF", fll=True,
         foff="N*10e3/samp_rate", ch_comment="п.2.7.7: расстройка N·10 кГц (относительная)"),
    dict(fname="lab5_2_7_8_qpsk_sdr.grc", id="lab5_2_7_8_qpsk_sdr",
         title="ЛР5 п.2.7.8  QPSK через SDR (HackRF -> RTL-SDR)", M=4, ss_bw="0.045", sdr=True,
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF", fll=True),
    dict(fname="lab5_2_7_9_qpsk_two_ones.grc", id="lab5_2_7_9_qpsk_two_ones",
         title="ЛР5 п.2.7.9  QPSK: передача «1, 1»", M=4, ss_bw="0.045", N_var=True, const="ordered",
         diff="True", decode=True, packed="(0b01010101,)",
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF", fll=True,
         foff="N*10e3/samp_rate"),
    dict(fname="lab5_2_7_10_8psk_two_sixes.grc", id="lab5_2_7_10_8psk_two_sixes",
         title="ЛР5 п.2.7.10  8PSK: передача «6, 6»", M=8, ss_bw="0.045", costas_w="0.251", N_var=True, const="ordered",
         diff="True", decode=True, packed="(0b11011011, 0b01101101, 0b10110110)",
         ted="digital.TED_GARDNER", resamp="digital.IR_PFB_MF", fll=True,
         foff="N*10e3/samp_rate", costas_comment="петля Костаса 8-го порядка"),
]

if __name__ == "__main__":
    fg_dqpsk("base").save("lab5_1_dqpsk.grc")
    fg_dqpsk("phase").save("lab5_1_9_3_dqpsk_phase.grc")
    fg_dqpsk("one").save("lab5_1_9_4_dqpsk_one_symbol.grc")
    fg_dqpsk("sdr").save("lab5_1_9_5_dqpsk_sdr.grc")
    fg_dqpsk("het").save("lab5_1_9_1_dqpsk_heterodyne.grc")
    fg_dqpsk_fll().save("lab5_1_9_1_dqpsk_fll.grc")
    fg_dqpsk_fll_simple().save("lab5_1_9_1_dqpsk_fll_simple.grc")
    for p in PART2:
        fg_mpsk(p).save(p["fname"])
