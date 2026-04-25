//+------------------------------------------------------------------+
//|  TRADESWITHMK XAU INTEL BOT                                      |
//|  Expert Advisor — XAU/USD Only                                   |
//|  Connects to Python/FastAPI backend for signal validation         |
//+------------------------------------------------------------------+
#property copyright "TRADESWITHMK"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Indicators\Trend.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                  |
//+------------------------------------------------------------------+

// ── Backend Connection
input string   InpBackendURL        = "http://127.0.0.1:8000";  // FastAPI backend URL
input string   InpApiToken          = "";                         // API auth token
input int      InpHttpTimeout       = 5000;                       // HTTP timeout ms

// ── Bot Mode
input ENUM_BOT_MODE InpBotMode      = MODE_ALERT_ONLY;  // Trading Mode
input bool     InpPaperTrading      = true;               // Paper trading (no real orders)
input bool     InpKillSwitch        = false;              // KILL SWITCH — halt all

// ── Risk
input double   InpRiskPerTrade      = 0.5;    // Risk per trade (%)
input double   InpMaxDailyLoss      = 2.0;    // Max daily loss (%)
input double   InpMaxDailyProfit    = 4.0;    // Max daily profit (%)
input int      InpMaxTradesPerDay   = 6;      // Max trades per day
input int      InpMaxConsecLosses   = 3;      // Max consecutive losses
input double   InpMaxSpreadPoints   = 35.0;   // Max spread in points
input double   InpMaxSlippage       = 20.0;   // Max slippage in points
input double   InpBreakEvenAtR      = 1.0;    // Break-even at X * R
input bool     InpTrailingAfterTP1  = true;   // Trailing stop after TP1

// ── Technical
input int      InpEMAFast           = 8;
input int      InpEMAMid            = 21;
input int      InpEMASlow           = 55;
input int      InpADXPeriod         = 14;
input double   InpADXMin            = 20.0;
input int      InpATRPeriod         = 14;
input double   InpSpikeATRMult      = 2.0;    // Spike = candle > X * ATR
input int      InpAsianStartHour    = 0;      // UTC
input int      InpAsianEndHour      = 8;
input int      InpLondonStartHour   = 7;
input int      InpLondonEndHour     = 12;
input int      InpNYStartHour       = 12;
input int      InpNYEndHour         = 17;

// ── Confluence
input int      InpMinScore          = 75;     // Minimum score to execute
input int      InpAlertScore        = 60;     // Minimum score to alert

// ── Signal refresh
input int      InpSignalBarShift    = 0;      // 0 = current bar

//+------------------------------------------------------------------+
//| ENUMERATIONS                                                      |
//+------------------------------------------------------------------+

enum ENUM_BOT_MODE
{
    MODE_ALERT_ONLY  = 0,  // Alert Only
    MODE_SEMI_AUTO   = 1,  // Semi-Auto (Telegram approval)
    MODE_FULL_AUTO   = 2,  // Full Auto
};

enum ENUM_SESSION
{
    SESSION_ASIAN   = 0,
    SESSION_LONDON  = 1,
    SESSION_NY      = 2,
    SESSION_OVERLAP = 3,
    SESSION_OFF     = 4,
};

enum ENUM_DIRECTION { DIR_NONE, DIR_BUY, DIR_SELL };

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES                                                  |
//+------------------------------------------------------------------+

CTrade      Trade;
CPositionInfo PosInfo;

// Indicator handles
int g_EMA8_Handle_M1, g_EMA21_Handle_M1, g_EMA55_Handle_M1;
int g_EMA8_Handle_M5, g_EMA21_Handle_M5, g_EMA55_Handle_M5;
int g_ADX_Handle_M5;
int g_ATR_Handle_M5;

// State tracking
datetime g_LastBarTime    = 0;
int      g_TodayTrades    = 0;
int      g_ConsecLosses   = 0;
double   g_DailyPnL       = 0.0;
double   g_OpenBalance    = 0.0;
string   g_LastSignalID   = "";
bool     g_BreakEvenSet   = false;
bool     g_TP1Hit         = false;

// Asian range
double   g_AsianHigh      = 0.0;
double   g_AsianLow       = 1e9;
bool     g_AsianRangeSet  = false;
datetime g_AsianRangeDate = 0;

// ICT cache
bool     g_HasBOS         = false;
bool     g_HasCHoCH       = false;
bool     g_HasFVG         = false;
double   g_FVG_High       = 0.0;
double   g_FVG_Low        = 0.0;
bool     g_HasOB          = false;
double   g_OB_High        = 0.0;
double   g_OB_Low         = 0.0;
bool     g_HasSweep       = false;
string   g_SweepDir       = "";

// Current open trade
string   g_OpenTradeID    = "";
double   g_TradeEntry     = 0.0;
double   g_TradeSL        = 0.0;
double   g_TradeTP1       = 0.0;
double   g_TradeTP2       = 0.0;
double   g_TradeTP3       = 0.0;
double   g_TradeLots      = 0.0;

//+------------------------------------------------------------------+
//| INIT                                                              |
//+------------------------------------------------------------------+

int OnInit()
{
    if(_Symbol != "XAUUSD" && _Symbol != "XAUUSDm" && _Symbol != "GOLD")
    {
        Alert("ERROR: This EA only trades XAU/USD. Current symbol: ", _Symbol);
        return INIT_FAILED;
    }

    Trade.SetExpertMagicNumber(202501);
    Trade.SetDeviationInPoints((long)InpMaxSlippage);
    Trade.SetTypeFilling(ORDER_FILLING_IOC);

    // Indicator handles
    g_EMA8_Handle_M1  = iMA(_Symbol, PERIOD_M1,  InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
    g_EMA21_Handle_M1 = iMA(_Symbol, PERIOD_M1,  InpEMAMid,  0, MODE_EMA, PRICE_CLOSE);
    g_EMA55_Handle_M1 = iMA(_Symbol, PERIOD_M1,  InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
    g_EMA8_Handle_M5  = iMA(_Symbol, PERIOD_M5,  InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
    g_EMA21_Handle_M5 = iMA(_Symbol, PERIOD_M5,  InpEMAMid,  0, MODE_EMA, PRICE_CLOSE);
    g_EMA55_Handle_M5 = iMA(_Symbol, PERIOD_M5,  InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
    g_ADX_Handle_M5   = iADX(_Symbol, PERIOD_M5, InpADXPeriod);
    g_ATR_Handle_M5   = iATR(_Symbol, PERIOD_M5, InpATRPeriod);

    if(g_EMA8_Handle_M5 == INVALID_HANDLE || g_ADX_Handle_M5 == INVALID_HANDLE)
    {
        Print("Failed to create indicator handles");
        return INIT_FAILED;
    }

    g_OpenBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    g_DailyPnL    = 0.0;

    Print("TRADESWITHMK XAU INTEL BOT initialized. Mode=", EnumToString(InpBotMode),
          " Paper=", InpPaperTrading);

    EventSetTimer(60);  // Heartbeat every 60s
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| DEINIT                                                            |
//+------------------------------------------------------------------+

void OnDeinit(const int reason)
{
    IndicatorRelease(g_EMA8_Handle_M1);
    IndicatorRelease(g_EMA21_Handle_M1);
    IndicatorRelease(g_EMA55_Handle_M1);
    IndicatorRelease(g_EMA8_Handle_M5);
    IndicatorRelease(g_EMA21_Handle_M5);
    IndicatorRelease(g_EMA55_Handle_M5);
    IndicatorRelease(g_ADX_Handle_M5);
    IndicatorRelease(g_ATR_Handle_M5);
    EventKillTimer();
    Print("TRADESWITHMK Bot deinitialized. Reason=", reason);
}

//+------------------------------------------------------------------+
//| TIMER — Heartbeat / account sync                                  |
//+------------------------------------------------------------------+

void OnTimer()
{
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
    SendAccountUpdate(balance, equity);
    ManageOpenTrades();
}

//+------------------------------------------------------------------+
//| MAIN TICK                                                         |
//+------------------------------------------------------------------+

void OnTick()
{
    if(InpKillSwitch) return;

    // Only process on new M5 bar
    datetime barTime = iTime(_Symbol, PERIOD_M5, 0);
    if(barTime == g_LastBarTime) return;
    g_LastBarTime = barTime;

    // Reset daily stats at midnight UTC
    ResetDailyStats();

    // Update Asian range
    UpdateAsianRange();

    // Compute ICT features
    ComputeICTFeatures();

    // Build market snapshot and call backend
    if(!HasOpenPosition())
    {
        MarketSnapshot snap = BuildMarketSnapshot();
        string response = CallBackendSignal(snap);
        ProcessBackendResponse(response, snap);
    }
    else
    {
        // Manage existing position
        ManageOpenTrades();
    }
}

//+------------------------------------------------------------------+
//| BUILD MARKET SNAPSHOT                                             |
//+------------------------------------------------------------------+

struct MarketSnapshot
{
    double bid, ask, spread;
    double ema8, ema21, ema55;
    double adx, atr;
    double high, low, open_p, close_p;
    double candleBody, wickHigh, wickLow;
    long   tickVol;
    string session;
    bool   isKillzone;
    string marketBias;
    bool   hasBOS, hasCHoCH, hasFVG, hasOB, hasSweep;
    double fvgH, fvgL, obH, obL;
    string sweepDir;
    bool   isPremium, isDiscount;
    double asianHigh, asianLow;
    bool   asianRangeSet;
    double balance, equity;
};

MarketSnapshot BuildMarketSnapshot()
{
    MarketSnapshot s;
    s.bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    s.ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    s.spread = (s.ask - s.bid) / _Point;

    double buf[1];
    CopyBuffer(g_EMA8_Handle_M5,  0, 0, 1, buf); s.ema8  = buf[0];
    CopyBuffer(g_EMA21_Handle_M5, 0, 0, 1, buf); s.ema21 = buf[0];
    CopyBuffer(g_EMA55_Handle_M5, 0, 0, 1, buf); s.ema55 = buf[0];

    double adxBuf[1];
    CopyBuffer(g_ADX_Handle_M5, 0, 0, 1, adxBuf); s.adx = adxBuf[0];

    double atrBuf[1];
    CopyBuffer(g_ATR_Handle_M5, 0, 0, 1, atrBuf); s.atr = atrBuf[0];

    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    CopyRates(_Symbol, PERIOD_M5, 0, 2, rates);
    s.high   = rates[1].high;
    s.low    = rates[1].low;
    s.open_p = rates[1].open;
    s.close_p = rates[1].close;
    s.candleBody = MathAbs(rates[1].close - rates[1].open);
    s.wickHigh   = rates[1].high - MathMax(rates[1].open, rates[1].close);
    s.wickLow    = MathMin(rates[1].open, rates[1].close) - rates[1].low;
    s.tickVol    = rates[1].tick_volume;

    s.session    = GetCurrentSession();
    s.isKillzone = IsKillzone();

    // Market bias from EMA alignment
    if(s.ema8 > s.ema21 && s.ema21 > s.ema55) s.marketBias = "bullish";
    else if(s.ema8 < s.ema21 && s.ema21 < s.ema55) s.marketBias = "bearish";
    else s.marketBias = "neutral";

    s.hasBOS    = g_HasBOS;
    s.hasCHoCH  = g_HasCHoCH;
    s.hasFVG    = g_HasFVG;
    s.fvgH      = g_FVG_High;
    s.fvgL      = g_FVG_Low;
    s.hasOB     = g_HasOB;
    s.obH       = g_OB_High;
    s.obL       = g_OB_Low;
    s.hasSweep  = g_HasSweep;
    s.sweepDir  = g_SweepDir;

    // Premium/Discount relative to Asian range
    if(g_AsianRangeSet && g_AsianHigh > g_AsianLow)
    {
        double mid = (g_AsianHigh + g_AsianLow) / 2.0;
        s.isPremium  = s.bid > mid + (g_AsianHigh - g_AsianLow) * 0.25;
        s.isDiscount = s.bid < mid - (g_AsianHigh - g_AsianLow) * 0.25;
    }

    s.asianHigh     = g_AsianHigh;
    s.asianLow      = g_AsianLow;
    s.asianRangeSet = g_AsianRangeSet;
    s.balance       = AccountInfoDouble(ACCOUNT_BALANCE);
    s.equity        = AccountInfoDouble(ACCOUNT_EQUITY);

    return s;
}

//+------------------------------------------------------------------+
//| SESSION DETECTION                                                 |
//+------------------------------------------------------------------+

string GetCurrentSession()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int h = dt.hour;

    bool london = (h >= InpLondonStartHour && h < InpLondonEndHour);
    bool ny     = (h >= InpNYStartHour     && h < InpNYEndHour);
    bool asian  = (h >= InpAsianStartHour  && h < InpAsianEndHour);

    if(london && ny) return "OVERLAP";
    if(london)       return "LONDON";
    if(ny)           return "NY";
    if(asian)        return "ASIAN";
    return "OFF";
}

bool IsKillzone()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int h = dt.hour;
    int m = dt.min;
    int hhmm = h * 100 + m;
    // London open: 07:00–09:00 | NY open: 12:00–14:00 | London close: 15:00–16:00
    return (hhmm >= 700  && hhmm < 900)  ||
           (hhmm >= 1200 && hhmm < 1400) ||
           (hhmm >= 1500 && hhmm < 1600);
}

//+------------------------------------------------------------------+
//| ASIAN RANGE TRACKING                                              |
//+------------------------------------------------------------------+

void UpdateAsianRange()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int h = dt.hour;

    // Reset at start of Asian session each day
    datetime today = StringToTime(
        TimeToString(TimeGMT(), TIME_DATE)
    );
    if(today != g_AsianRangeDate)
    {
        g_AsianHigh     = 0.0;
        g_AsianLow      = 1e9;
        g_AsianRangeSet = false;
        g_AsianRangeDate = today;
    }

    if(h < InpAsianStartHour || h >= InpAsianEndHour) return;

    double high = iHigh(_Symbol, PERIOD_M5, 0);
    double low  = iLow (_Symbol, PERIOD_M5, 0);
    if(high > g_AsianHigh) g_AsianHigh = high;
    if(low  < g_AsianLow)  g_AsianLow  = low;

    // Mark range as set once we're past the Asian session midpoint
    if(h >= (InpAsianStartHour + InpAsianEndHour) / 2)
        g_AsianRangeSet = true;
}

//+------------------------------------------------------------------+
//| ICT FEATURE COMPUTATION                                           |
//+------------------------------------------------------------------+

void ComputeICTFeatures()
{
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(_Symbol, PERIOD_M5, 0, 30, rates);
    if(copied < 10) return;

    // ── Break of Structure (BOS) ──────────────────────────────────
    // Simple: recent swing high broken = bullish BOS
    double swingHigh = 0.0, swingLow = 1e9;
    for(int i = 2; i < 10; i++)
    {
        if(rates[i].high > swingHigh) swingHigh = rates[i].high;
        if(rates[i].low  < swingLow)  swingLow  = rates[i].low;
    }
    double curClose = rates[0].close;
    g_HasBOS   = (curClose > swingHigh) || (curClose < swingLow);
    g_HasCHoCH = false;  // CHoCH requires more complex logic — simplified here

    // Detect overall trend shift for CHoCH
    double prev2High = 0.0, prev2Low = 1e9;
    for(int i = 10; i < 20; i++)
    {
        if(rates[i].high > prev2High) prev2High = rates[i].high;
        if(rates[i].low  < prev2Low)  prev2Low  = rates[i].low;
    }
    if((curClose > swingHigh && swingLow > prev2Low) ||
       (curClose < swingLow  && swingHigh < prev2High))
        g_HasCHoCH = true;

    // ── Fair Value Gap (FVG) ──────────────────────────────────────
    // 3-candle pattern: gap between candle[2].high and candle[0].low (bullish FVG)
    g_HasFVG = false;
    if(copied >= 3)
    {
        // Bullish FVG: rates[2].high < rates[0].low
        if(rates[2].high < rates[0].low - _Point * 50)
        {
            g_HasFVG  = true;
            g_FVG_Low  = rates[2].high;
            g_FVG_High = rates[0].low;
        }
        // Bearish FVG: rates[2].low > rates[0].high
        else if(rates[2].low > rates[0].high + _Point * 50)
        {
            g_HasFVG  = true;
            g_FVG_High = rates[2].low;
            g_FVG_Low  = rates[0].high;
        }
    }

    // ── Order Block (OB) ─────────────────────────────────────────
    // Last bearish candle before a bullish impulse (bullish OB)
    g_HasOB = false;
    for(int i = 3; i < 15; i++)
    {
        bool isImpluse = (rates[i-2].close - rates[i-2].open) > 0 &&
                         MathAbs(rates[i-2].close - rates[i-2].open) > rates[i-2].high - rates[i-2].low * 0.5;
        bool isBearCandle = rates[i].close < rates[i].open;
        if(isBearCandle && isImpluse)
        {
            g_HasOB  = true;
            g_OB_High = rates[i].high;
            g_OB_Low  = rates[i].low;
            break;
        }
    }

    // ── Liquidity Sweep ───────────────────────────────────────────
    g_HasSweep = false;
    g_SweepDir = "";
    if(g_AsianRangeSet)
    {
        double recentHigh = 0.0, recentLow = 1e9;
        for(int i = 0; i < 5; i++)
        {
            if(rates[i].high > recentHigh) recentHigh = rates[i].high;
            if(rates[i].low  < recentLow)  recentLow  = rates[i].low;
        }
        // Swept above Asian high and returned below
        if(recentHigh > g_AsianHigh && rates[0].close < g_AsianHigh)
        {
            g_HasSweep = true;
            g_SweepDir = "HIGH";
        }
        // Swept below Asian low and returned above
        else if(recentLow < g_AsianLow && rates[0].close > g_AsianLow)
        {
            g_HasSweep = true;
            g_SweepDir = "LOW";
        }
    }
}

//+------------------------------------------------------------------+
//| CALL BACKEND — /signal/process                                    |
//+------------------------------------------------------------------+

string SnapToJSON(MarketSnapshot &s)
{
    string j = "{";
    j += "\"symbol\":\"" + _Symbol + "\",";
    j += "\"bid\":"      + DoubleToString(s.bid, 3)    + ",";
    j += "\"ask\":"      + DoubleToString(s.ask, 3)    + ",";
    j += "\"spread\":"   + DoubleToString(s.spread, 1) + ",";
    j += "\"time\":\""   + TimeToString(TimeGMT(), TIME_DATE|TIME_MINUTES) + "\",";
    j += "\"timeframe\":\"M5\",";
    j += "\"high\":"     + DoubleToString(s.high, 3)   + ",";
    j += "\"low\":"      + DoubleToString(s.low, 3)    + ",";
    j += "\"open\":"     + DoubleToString(s.open_p, 3) + ",";
    j += "\"close\":"    + DoubleToString(s.close_p,3) + ",";
    j += "\"ema8\":"     + DoubleToString(s.ema8, 3)   + ",";
    j += "\"ema21\":"    + DoubleToString(s.ema21, 3)  + ",";
    j += "\"ema55\":"    + DoubleToString(s.ema55, 3)  + ",";
    j += "\"adx\":"      + DoubleToString(s.adx, 2)    + ",";
    j += "\"atr\":"      + DoubleToString(s.atr, 3)    + ",";
    j += "\"last_candle_body\":"     + DoubleToString(s.candleBody, 3) + ",";
    j += "\"last_candle_wick_high\":" + DoubleToString(s.wickHigh, 3) + ",";
    j += "\"last_candle_wick_low\":"  + DoubleToString(s.wickLow, 3)  + ",";
    j += "\"tick_volume\":"  + IntegerToString(s.tickVol) + ",";
    j += "\"session\":\""    + s.session + "\",";
    j += "\"is_killzone\":"  + (s.isKillzone ? "true" : "false") + ",";
    j += "\"market_bias\":\"" + s.marketBias + "\",";
    j += "\"has_bos\":"      + (s.hasBOS   ? "true" : "false") + ",";
    j += "\"has_choch\":"    + (s.hasCHoCH ? "true" : "false") + ",";
    j += "\"has_fvg\":"      + (s.hasFVG   ? "true" : "false") + ",";
    j += "\"fvg_high\":"     + DoubleToString(s.fvgH, 3) + ",";
    j += "\"fvg_low\":"      + DoubleToString(s.fvgL, 3) + ",";
    j += "\"has_order_block\":" + (s.hasOB ? "true" : "false") + ",";
    j += "\"ob_high\":"      + DoubleToString(s.obH, 3) + ",";
    j += "\"ob_low\":"       + DoubleToString(s.obL, 3) + ",";
    j += "\"has_liquidity_sweep\":" + (s.hasSweep ? "true" : "false") + ",";
    j += "\"sweep_direction\":\"" + s.sweepDir + "\",";
    j += "\"is_premium\":"   + (s.isPremium  ? "true" : "false") + ",";
    j += "\"is_discount\":"  + (s.isDiscount ? "true" : "false") + ",";
    j += "\"asian_high\":"   + DoubleToString(s.asianHigh, 3) + ",";
    j += "\"asian_low\":"    + DoubleToString(s.asianLow, 3)  + ",";
    j += "\"asian_range_set\":" + (s.asianRangeSet ? "true" : "false") + ",";
    j += "\"dxy_bias\":\"neutral\",";   // DXY = confirmation only, never primary
    j += "\"balance\":"  + DoubleToString(s.balance, 2) + ",";
    j += "\"equity\":"   + DoubleToString(s.equity, 2);
    j += "}";
    return j;
}

string CallBackendSignal(MarketSnapshot &snap)
{
    string url     = InpBackendURL + "/signal/process";
    string payload = SnapToJSON(snap);
    char   postData[];
    StringToCharArray(payload, postData, 0, StringLen(payload));

    string headers  = "Content-Type: application/json\r\nX-Api-Token: " + InpApiToken + "\r\n";
    char   result[];
    string resHeaders;
    int    timeout  = InpHttpTimeout;
    int    code     = WebRequest("POST", url, headers, timeout, postData, result, resHeaders);

    if(code != 200)
    {
        Print("Backend error. HTTP=", code, " URL=", url);
        return "";
    }
    return CharArrayToString(result);
}

//+------------------------------------------------------------------+
//| PROCESS BACKEND RESPONSE                                          |
//+------------------------------------------------------------------+

void ProcessBackendResponse(string response, MarketSnapshot &snap)
{
    if(StringLen(response) == 0) return;

    string action = JSONGetString(response, "action");

    if(action == "HALT" || action == "BLOCKED")
    {
        string reason = JSONGetString(response, "reason");
        Print("Trade blocked: ", reason);
        return;
    }

    if(action == "NO_SIGNAL") return;

    if(action == "ALERT")
    {
        Print("Signal detected (Alert Only) — no execution");
        return;
    }

    if(action == "AWAIT_APPROVAL")
    {
        Print("Signal sent to Telegram for approval (Semi-Auto mode)");
        return;
    }

    if(action == "EXECUTE")
    {
        string signal    = JSONGetString(response, "signal");
        string direction = JSONGetString(signal, "direction");
        double entry     = JSONGetDouble(signal, "entry");
        double sl        = JSONGetDouble(signal, "sl");
        double tp1       = JSONGetDouble(signal, "tp1");
        double tp2       = JSONGetDouble(signal, "tp2");
        double tp3       = JSONGetDouble(signal, "tp3");
        double lots      = JSONGetDouble(response, "lot_size");
        string signalID  = JSONGetString(signal, "signal_id");
        string strategy  = JSONGetString(signal, "strategy");
        int    score     = (int)JSONGetDouble(signal, "confluence_score");
        string reasoning = JSONGetString(signal, "reasoning");

        if(InpPaperTrading)
        {
            Print("PAPER TRADE: ", direction, " lots=", lots,
                  " entry=", entry, " SL=", sl, " TP1=", tp1,
                  " Score=", score, "/100");
            NotifyTradeOpen(signalID, direction, entry, sl, tp1, tp2, tp3,
                           lots, InpRiskPerTrade, score, strategy, reasoning);
            return;
        }

        ExecuteTrade(direction, lots, sl, tp1, tp2, tp3,
                     signalID, strategy, score, reasoning);
    }
}

//+------------------------------------------------------------------+
//| EXECUTE TRADE                                                     |
//+------------------------------------------------------------------+

void ExecuteTrade(
    string direction, double lots, double sl,
    double tp1, double tp2, double tp3,
    string signalID, string strategy, int score, string reasoning)
{
    // Final safety checks before firing
    double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                     SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
    if(spread > InpMaxSpreadPoints)
    {
        Print("Trade aborted: spread too wide (", spread, " pts)");
        return;
    }

    if(HasOpenPosition()) { Print("Already have an open position"); return; }

    bool ok = false;
    if(direction == "BUY")
    {
        double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        ok = Trade.Buy(lots, _Symbol, price, sl, tp1, "TWMK|" + signalID);
    }
    else if(direction == "SELL")
    {
        double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        ok = Trade.Sell(lots, _Symbol, price, sl, tp1, "TWMK|" + signalID);
    }

    if(ok)
    {
        g_OpenTradeID = signalID;
        g_TradeEntry  = (direction == "BUY") ?
            SymbolInfoDouble(_Symbol, SYMBOL_ASK) :
            SymbolInfoDouble(_Symbol, SYMBOL_BID);
        g_TradeSL     = sl;
        g_TradeTP1    = tp1;
        g_TradeTP2    = tp2;
        g_TradeTP3    = tp3;
        g_TradeLots   = lots;
        g_BreakEvenSet = false;
        g_TP1Hit      = false;
        g_TodayTrades++;

        NotifyTradeOpen(signalID, direction, g_TradeEntry, sl, tp1, tp2, tp3,
                       lots, InpRiskPerTrade, score, strategy, reasoning);
        Print("Trade OPENED: ", direction, " lots=", lots, " score=", score);
    }
    else
    {
        Print("Trade FAILED: ", Trade.ResultRetcode(), " ", Trade.ResultRetcodeDescription());
    }
}

//+------------------------------------------------------------------+
//| MANAGE OPEN TRADES                                                |
//+------------------------------------------------------------------+

void ManageOpenTrades()
{
    if(g_OpenTradeID == "") return;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(!PosInfo.SelectByIndex(i)) continue;
        if(PosInfo.Symbol() != _Symbol) continue;
        if(PosInfo.Magic() != 202501) continue;

        double price = (PosInfo.PositionType() == POSITION_TYPE_BUY) ?
            SymbolInfoDouble(_Symbol, SYMBOL_BID) :
            SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        double entry = PosInfo.PriceOpen();
        double sl    = PosInfo.StopLoss();
        ulong  ticket= PosInfo.Ticket();

        // Break-even check
        if(!g_BreakEvenSet)
        {
            double r   = MathAbs(g_TradeTP1 - entry);
            bool   at1r = (PosInfo.PositionType() == POSITION_TYPE_BUY) ?
                          (price >= entry + r * InpBreakEvenAtR) :
                          (price <= entry - r * InpBreakEvenAtR);
            if(at1r)
            {
                double newSL = entry + _Point * 2;  // tiny buffer above entry
                if(PosInfo.PositionType() == POSITION_TYPE_SELL)
                    newSL = entry - _Point * 2;
                if(Trade.PositionModify(ticket, newSL, g_TradeTP2))
                {
                    g_BreakEvenSet = true;
                    Print("Break-even set at ", newSL);
                    NotifyBreakEven(g_OpenTradeID, newSL);
                }
            }
        }

        // TP1 partial close (50%)
        if(!g_TP1Hit)
        {
            bool hitTP1 = (PosInfo.PositionType() == POSITION_TYPE_BUY) ?
                          (price >= g_TradeTP1) : (price <= g_TradeTP1);
            if(hitTP1)
            {
                double closeVol = NormalizeDouble(PosInfo.Volume() * 0.5, 2);
                if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
                {
                    if(Trade.PositionClosePartial(ticket, closeVol))
                    {
                        g_TP1Hit = true;
                        double pnl = PosInfo.Profit() * 0.5;
                        NotifyTPHit(g_OpenTradeID, 1, price, pnl);
                        Print("TP1 partial close: ", closeVol, " lots");
                    }
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| POSITION CHECK                                                    |
//+------------------------------------------------------------------+

bool HasOpenPosition()
{
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionGetSymbol(i) == _Symbol &&
           PositionGetInteger(POSITION_MAGIC) == 202501)
            return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| DAILY STATS RESET                                                 |
//+------------------------------------------------------------------+

void ResetDailyStats()
{
    static datetime lastResetDay = 0;
    datetime todayStart = StringToTime(TimeToString(TimeGMT(), TIME_DATE));
    if(todayStart > lastResetDay)
    {
        lastResetDay   = todayStart;
        g_TodayTrades  = 0;
        g_DailyPnL     = 0.0;
        g_OpenBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
        g_ConsecLosses = 0;
        Print("Daily stats reset");
    }
}

//+------------------------------------------------------------------+
//| BACKEND NOTIFICATIONS                                             |
//+------------------------------------------------------------------+

void SendAccountUpdate(double balance, double equity)
{
    string url     = InpBackendURL + "/account/update";
    string payload = "{\"balance\":" + DoubleToString(balance, 2) +
                     ",\"equity\":"  + DoubleToString(equity, 2) + "}";
    char   postData[], result[];
    StringToCharArray(payload, postData, 0, StringLen(payload));
    string headers = "Content-Type: application/json\r\nX-Api-Token: " + InpApiToken + "\r\n";
    string resH;
    WebRequest("POST", url, headers, InpHttpTimeout, postData, result, resH);
}

void NotifyTradeOpen(
    string id, string dir, double entry, double sl,
    double tp1, double tp2, double tp3,
    double lots, double riskPct, int score,
    string strategy, string reasoning)
{
    string url = InpBackendURL + "/trade/open";
    string payload = "{";
    payload += "\"trade_id\":\""    + id        + "\",";
    payload += "\"signal_id\":\""   + id        + "\",";
    payload += "\"direction\":\""   + dir       + "\",";
    payload += "\"entry\":"         + DoubleToString(entry, 3)   + ",";
    payload += "\"sl\":"            + DoubleToString(sl, 3)      + ",";
    payload += "\"tp1\":"           + DoubleToString(tp1, 3)     + ",";
    payload += "\"tp2\":"           + DoubleToString(tp2, 3)     + ",";
    payload += "\"tp3\":"           + DoubleToString(tp3, 3)     + ",";
    payload += "\"lot_size\":"      + DoubleToString(lots, 2)    + ",";
    payload += "\"risk_pct\":"      + DoubleToString(riskPct, 2) + ",";
    payload += "\"confluence_score\":" + IntegerToString(score)  + ",";
    payload += "\"strategy\":\""   + strategy  + "\",";
    payload += "\"session\":\""    + GetCurrentSession() + "\",";
    payload += "\"reasoning\":\""  + EscapeJSON(reasoning) + "\"";
    payload += "}";

    char postData[], result[];
    StringToCharArray(payload, postData, 0, StringLen(payload));
    string headers = "Content-Type: application/json\r\nX-Api-Token: " + InpApiToken + "\r\n";
    string resH;
    WebRequest("POST", url, headers, InpHttpTimeout, postData, result, resH);
}

void NotifyTradeClose(string id, double closePrice, double pnl, string status)
{
    string url = InpBackendURL + "/trade/close";
    string payload = "{\"trade_id\":\"" + id + "\","
                   + "\"close_price\":" + DoubleToString(closePrice, 3) + ","
                   + "\"pnl\":"         + DoubleToString(pnl, 2) + ","
                   + "\"status\":\""    + status + "\"}";
    char postData[], result[];
    StringToCharArray(payload, postData, 0, StringLen(payload));
    string headers = "Content-Type: application/json\r\nX-Api-Token: " + InpApiToken + "\r\n";
    string resH;
    WebRequest("POST", url, headers, InpHttpTimeout, postData, result, resH);
}

void NotifyBreakEven(string id, double price)
{
    NotifyTradeClose(id, price, 0.0, "BE");
}

void NotifyTPHit(string id, int level, double price, double pnl)
{
    string status = "TP" + IntegerToString(level);
    NotifyTradeClose(id, price, pnl, status);
}

//+------------------------------------------------------------------+
//| TRADE EVENTS                                                      |
//+------------------------------------------------------------------+

void OnTradeTransaction(
    const MqlTradeTransaction &trans,
    const MqlTradeRequest &request,
    const MqlTradeResult &result)
{
    if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
    if(trans.symbol != _Symbol) return;

    ulong dealTicket = trans.deal;
    if(!HistoryDealSelect(dealTicket)) return;

    long dealMagic  = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
    if(dealMagic != 202501) return;

    long   entry    = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
    double price    = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
    double profit   = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);

    if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
    {
        string status = "MANUAL";
        if(profit > 0)
        {
            if(!g_TP1Hit)       status = "TP1";
            else if(g_TP1Hit)   status = "TP2";
        }
        else if(profit < 0) status = "SL";

        g_DailyPnL += profit;
        if(profit < 0) g_ConsecLosses++;
        else           g_ConsecLosses = 0;

        NotifyTradeClose(g_OpenTradeID, price, profit, status);
        g_OpenTradeID = "";
        g_BreakEvenSet = false;
        g_TP1Hit = false;

        Print("Trade closed: ", status, " PnL=", profit, " DailyPnL=", g_DailyPnL);
    }
}

//+------------------------------------------------------------------+
//| SIMPLE JSON HELPERS                                               |
//+------------------------------------------------------------------+

string JSONGetString(string json, string key)
{
    string search = "\"" + key + "\":\"";
    int start = StringFind(json, search);
    if(start < 0) return "";
    start += StringLen(search);
    int end = StringFind(json, "\"", start);
    if(end < 0) return "";
    return StringSubstr(json, start, end - start);
}

double JSONGetDouble(string json, string key)
{
    string search = "\"" + key + "\":";
    int start = StringFind(json, search);
    if(start < 0) return 0.0;
    start += StringLen(search);
    // Skip whitespace
    while(start < StringLen(json) && StringGetCharacter(json, start) == ' ') start++;
    int end = start;
    while(end < StringLen(json))
    {
        ushort c = StringGetCharacter(json, end);
        if(c == ',' || c == '}' || c == ']') break;
        end++;
    }
    return StringToDouble(StringSubstr(json, start, end - start));
}

string EscapeJSON(string s)
{
    // Basic escaping for JSON string values
    StringReplace(s, "\\", "\\\\");
    StringReplace(s, "\"", "\\\"");
    StringReplace(s, "\n", "\\n");
    StringReplace(s, "\r", "");
    StringReplace(s, "\t", " ");
    return s;
}

//+------------------------------------------------------------------+
//| CHART EVENT — Info display                                        |
//+------------------------------------------------------------------+

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
    // Reserved for future dashboard overlay
}
