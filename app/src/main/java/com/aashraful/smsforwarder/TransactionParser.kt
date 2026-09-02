package com.aashraful.smsforwarder
object TransactionParser {
    data class Tx(val wallet:String,val type:String,val amount:Double,val txId:String,val balance:Double,val counterpart:String)
    fun parse(sender:String,body:String):Tx?{
        val sl=sender.lowercase();val bl=body.lowercase()
        val wallet=when{sl.contains("bkash")->"bKash";sl.contains("nagad")->"Nagad";else->return null}
        val amtRx=Regex("""(?:tk\.?\s*)([0-9,]+(?:\.[0-9]{1,2})?)""",RegexOption.IGNORE_CASE)
        val amount=amtRx.findAll(body).map{it.groupValues[1].replace(",","").toDoubleOrNull()?:0.0}.filter{it>0}.firstOrNull()?:0.0
        val balRx=Regex("""balance[:\s]+(?:tk\.?\s*)?([0-9,]+(?:\.[0-9]{1,2})?)""",RegexOption.IGNORE_CASE)
        val balance=balRx.find(body)?.groupValues?.get(1)?.replace(",","")?.toDoubleOrNull()?:0.0
        val txRx=Regex("""(?:ref(?:erence)?|trxid|txnid)[:\s#]*([A-Z0-9]+)""",RegexOption.IGNORE_CASE)
        val txId=txRx.find(body)?.groupValues?.get(1)?:""
        val phoneRx=Regex("""(?:from|to)\s+(01[0-9]{9})""",RegexOption.IGNORE_CASE)
        val cp=phoneRx.find(body)?.groupValues?.get(1)?:""
        val type=when{bl.contains("received")||bl.contains("joma")->"receive";bl.contains("cashout")||bl.contains("withdrawn")||bl.contains("agent")->"cashout";bl.contains("sent")||bl.contains("send")->"send";bl.contains("paid")||bl.contains("payment")->"payment";else->"other"}
        return Tx(wallet,type,amount,txId,balance,cp)
    }
    fun typeIcon(t:String)=when(t){"receive"->"\uD83D\uDCE5";"cashout"->"\uD83C\uDFE7";"send"->"\uD83D\uDCE4";"payment"->"\uD83D\uDCB3";else->"\uD83D\uDCE8"}
    fun walletIcon(w:String)=if(w=="bKash")"\uD83D\uDC97" else "\uD83D\uDFE0"
    fun fmtAmount(a:Double)="\u09F3${String.format("%,.2f",a)}"
}