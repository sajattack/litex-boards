#!/usr/bin/env python3

# This file is Copyright (c) 2020 Paul Sajna <sajattack@gmail.com>
# License: BSD

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex_boards.platforms import de10nano

from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import AS4C16M16
from litedram.phy import GENSDRPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, with_sdram=False):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()
        self.clock_domains.cd_pix    = ClockDomain()
        self.clock_domains.cd_vga    = ClockDomain()

        # # #

        # Clk / Rst
        clk50 = platform.request("clk50")
        platform.add_period_constraint(clk50, 1e9/50e6)

        # PLL
        pll_locked  = Signal()
        pll_clk_out = Signal(6)
        self.specials += \
            Instance("ALTPLL",
                p_BANDWIDTH_TYPE         = "AUTO",
                p_CLK0_DIVIDE_BY         = 1,
                p_CLK0_DUTY_CYCLE        = 50,
                p_CLK0_MULTIPLY_BY       = 1,
                p_CLK0_PHASE_SHIFT       = "0",
                p_CLK1_DIVIDE_BY         = 1,
                p_CLK1_DUTY_CYCLE        = 50,
                p_CLK1_MULTIPLY_BY       = 1,
                p_CLK1_PHASE_SHIFT       = "-10000",
                p_CLK2_DIVIDE_BY         = 2, # 240p/60hz pixclk
                p_CLK2_MULTIPLY_BY       = 1,
                p_CLK2_PHASE_SHIFT       = "0",
                p_COMPENSATE_CLOCK       = "CLK0",
                p_INCLK0_INPUT_FREQUENCY = 20000,
                p_OPERATION_MODE         = "NORMAL",
                i_INCLK                  = clk50,
                o_CLK                    = pll_clk_out,
                i_ARESET                 = 0,
                i_CLKENA                 = 0x3f,
                i_EXTCLKENA              = 0xf,
                i_FBIN                   = 1,
                i_PFDENA                 = 1,
                i_PLLENA                 = 1,
                o_LOCKED                 = pll_locked,
            )
        self.comb += [
            self.cd_sys.clk.eq(pll_clk_out[0]),
            self.cd_sys_ps.clk.eq(pll_clk_out[1]),
            self.cd_pix.clk.eq(pll_clk_out[2]),
            self.cd_vga.clk.eq(pll_clk_out[2])
        ]
        self.specials += [
            AsyncResetSynchronizer(self.cd_sys,    ~pll_locked),
            AsyncResetSynchronizer(self.cd_sys_ps, ~pll_locked)
        ]

        if with_sdram:
            self.comb += platform.request("sdram_clock").eq(self.cd_sys_ps.clk)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=int(50e6), **kwargs):
        assert sys_clk_freq == int(50e6)
        platform = de10nano.Platform()

        # SoCCore ---------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform)

# MiSTerSDRAMSoC -----------------------------------------------------------------------------------

class MiSTerSDRAMSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(50e6), **kwargs):
        assert sys_clk_freq == int(50e6)
        platform = de10nano.Platform()

        # SoCSDRAM ---------------------------------------------------------------------------------
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, with_sdram=True)

        # SDR SDRAM --------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"))
            sdram_module = AS4C16M16(self.clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                geom_settings   = sdram_module.geom_settings,
                timing_settings = sdram_module.timing_settings)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on DE10 Nano")
    parser.add_argument("--with-mister-sdram", action="store_true",
                        help="enable MiSTer SDRAM expansion board")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()
    soc = None
    if args.with_mister_sdram:
        soc = MiSTerSDRAMSoC(**soc_sdram_argdict(args))
    else:
        soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
