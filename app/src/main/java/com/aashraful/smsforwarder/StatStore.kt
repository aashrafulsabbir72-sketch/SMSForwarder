package com.aashraful.smsforwarder
import android.content.Context
object StatStore {
    private const val P="sms_stat"
    fun add(ctx:Context,tx:TransactionParser.Tx){
        if(tx.amount<=0)return
        val k="${tx.wallet.lowercase()}_${tx.type}"
        val pr=ctx.getSharedPreferences(P,Context.MODE_PRIVATE)
        pr.edit().putFloat("${k}_amt",pr.getFloat("${k}_amt",0f)+tx.amount.toFloat())
            .putInt("${k}_cnt",pr.getInt("${k}_cnt",0)+1)
            .putFloat("${tx.wallet.lowercase()}_bal",tx.balance.toFloat()).apply()
    }
    fun todaySummary(ctx:Context):String{
        val pr=ctx.getSharedPreferences(P,Context.MODE_PRIVATE)
        val types=listOf("receive","send","cashout","payment","other")
        val wallets=listOf("bKash" to "\uD83D\uDC97","Nagad" to "\uD83D\uDFE0")
        val sb=StringBuilder();var gTotal=0.0;var gCount=0
        for((wallet,wIcon) in wallets){
            val wl=wallet.lowercase();val bal=pr.getFloat("${wl}_bal",-1f)
            var wTotal=0.0;var wCount=0;val wSb=StringBuilder()
            for(type in types){val amt=pr.getFloat("${wl}_${type}_amt",0f).toDouble();val cnt=pr.getInt("${wl}_${type}_cnt",0)
                if(cnt>0){wTotal+=amt;wCount+=cnt;wSb.append("  ${TransactionParser.typeIcon(type)} ${type.replaceFirstChar{it.uppercase()}}: ${cnt}x ${TransactionParser.fmtAmount(amt)}\n")}}
            if(wCount>0){sb.append("$wIcon <b>$wallet</b>: ${wCount}x ${TransactionParser.fmtAmount(wTotal)}\n$wSb")
                if(bal>=0)sb.append("  \uD83D\uDCB0 Balance: ${TransactionParser.fmtAmount(bal.toDouble())}\n")
                sb.append("\n");gTotal+=wTotal;gCount+=wCount}
        }
        return if(sb.isEmpty())"No parsed transactions today" else "Total: ${gCount}x ${TransactionParser.fmtAmount(gTotal)}\n\n$sb".trim()
    }
    fun reset(ctx:Context){ctx.getSharedPreferences(P,Context.MODE_PRIVATE).edit().clear().apply()}
    fun getBalance(ctx:Context,wallet:String)=ctx.getSharedPreferences(P,Context.MODE_PRIVATE).getFloat("${wallet.lowercase()}_bal",-1f).toDouble()
}