package fm.qingting.RecSysRankService.controllers
import com.redis.RedisClientPool
import org.apache.hadoop.hbase.HBaseConfiguration
import org.apache.hadoop.hbase.client.{Connection, ConnectionFactory}
import channelUpdateRateReSort.reChannelSort
import scala.collection.mutable.{Map => mutableMap}
import scala.concurrent.{Await, ExecutionContext, Future}
import scala.util.control.NonFatal
import play.api.libs.json._
import fm.qingting.RecSysNg.config.AppConfig.appConf

object MmrDiversity {
  //原始mmr打分
  def makeMmr(pool: RedisClientPool, chanelScoreMapRaw: Map[String, Float]): Seq[JsObject] = {
    try {
      val (channelScoreTop50Temp, channelScoreBackTemp) = chanelScoreMapRaw.toList.sortBy(_._2).reverse.splitAt(50)
      val channelScoreTop50Map = channelScoreTop50Temp.toMap.map(item => item._1.toInt -> item._2)
      val channelScoreBackList = channelScoreBackTemp.map(item => (item._1.toInt, item._2))
      //根据channel获取cf
      val channelCfMap = getCFMap(pool, channelScoreTop50Map.toList.map(item => item._1))
      //调用mmr
      val resTopK = MMR(channelScoreTop50Map, channelCfMap, 20, 0.995f)
      val resTopKRawScore = resTopK.map { item => (item, channelScoreTop50Map.getOrElse(item, 0.0f)) }
      (resTopKRawScore ++ channelScoreBackList).map(item => Json.obj("c" -> item._1, "s" -> item._2))
    }
    catch {
      case NonFatal(_) => chanelScoreMapRaw.toList.sortBy(_._2).reverse.map(item => Json.obj("c" -> item._1, "s" -> item._2))
    }
  }
  //乘以专辑rate的mmr打分
  def makeMmrWithRate(deviceId: String, hbaseConn: Connection, pool: RedisClientPool, chanelScoreMapRaw: Map[String, Float]): Seq[JsObject] = {
    try {
      val (channelScoreTop50Temp, channelScoreBackTemp) = chanelScoreMapRaw.toList.sortBy(_._2).reverse.splitAt(50)
      val channelScoreTop50Map = channelScoreTop50Temp.toMap.map(item => item._1.toInt -> item._2)
      val channelScoreBackList = channelScoreBackTemp.map(_._1.toInt)
      //根据channel获取cf
      val channelCfMap = getCFMap(pool, channelScoreTop50Map.toList.map(item => item._1))
      //调用mmr
      val resTopK = MMR(channelScoreTop50Map, channelCfMap, 20, 0.99f)
      val mmrRes = resTopK ++ channelScoreBackList
      val mmrWithRate = reChannelSort(deviceId, mmrRes, hbaseConn)
      val resSeq=mmrWithRate.map(item=>(item,chanelScoreMapRaw.getOrElse(item.toString,0.0f)))
      resSeq.map(item => Json.obj("c" -> item._1, "s" -> item._2))
    }
    catch {
      case NonFatal(_) => chanelScoreMapRaw.toList.sortBy(_._2).reverse.map(item => Json.obj("c" -> item._1, "s" -> item._2))
    }
  }

  //创建获取CF打分时用到的redis-pool
  def createRedisPool(): RedisClientPool = {
    val host = appConf.getString("online_redis.host")
    val port = appConf.getInt("online_redis.port")
    val auth = appConf.getString("online_redis.auth")
    new RedisClientPool(
      host = host,
      port = port,
      database = 0,
      secret = Some(auth),
      timeout = 3600
    )
  }

  //创建获取召回专辑信息的HbaseCon
  def createHbaseConn(): Connection = {
    // pipeline hbase  if only to use , need transfer to online hbase   !!!!!!!!!!!!!
    val ZOOKEEPER_QUORUM = appConf.getString("online_hbase.quorum")
    val ZNODE_PARENT = appConf.getString("online_hbase.znode_parent")
    val hbaseConf = HBaseConfiguration.create()
    hbaseConf.set("hbase.zookeeper.quorum", ZOOKEEPER_QUORUM)
    hbaseConf.set("zookeeper.znode.parent", ZNODE_PARENT)
    ConnectionFactory.createConnection(hbaseConf)
  }

  //获取专辑的CF打分值
  def getCFMap(pool: RedisClientPool, channelIds: Seq[Int]): Map[Int, Array[(Int, Float)]] = {
    pool.withClient { client =>
      val cfStrMap = client
        .hmget[Int, String]("allChannels:mmr_cf", channelIds: _*)
        .getOrElse(Map.empty)
        .filter(_._2.nonEmpty)
      cfStrMap.map {
        case (channelId, str) =>
          val data = str.split(",").map { s =>
            val a = s.split("_")
            a.head.toInt -> a.last.toFloat
          }
          channelId -> data
      }
    }
  }

  //max[lambda *sim1(Di,Q)-(1-lambda)*max Sim2(Di,Dj)]
  def MMR(chanelScore: Map[Int, Float], channelCF: Map[Int, Array[(Int, Float)]], topK: Int, lambda: Float): Seq[Int] = {
    if (chanelScore.size <= topK) {
      chanelScore.toSeq.sortBy(_._2).reverse.map(_._1)
    } else {
      var stateChannelScore: mutableMap[Int, Float] = mutableMap(chanelScore.toSeq: _*)
      var resTopKMap: mutableMap[Int, Float] = mutableMap()

      while (resTopKMap.size < topK) {
        var mmrScore = Float.MinValue //初始的专辑mmr分数
        var selectOne = stateChannelScore.keys.head //初始的专辑
        stateChannelScore.foreach { item =>
          //S中的Di
          val chanelId = item._1
          //Di对应的打分
          val sim1Score = item._2
          //Di对应的CF分数
          val sim2 = channelCF.getOrElse(chanelId, Array.empty[(Int, Float)]).toMap
          //在R中找到与Di分值差别最大的值
          var maxDiDj = 0.0f
          if (sim2.size == 0) {
            maxDiDj = 0
          } else {
            resTopKMap.foreach { resItem =>
              val dj = resItem._1
              val scoreDiDj = sim2.getOrElse(dj, 0.0f)
              maxDiDj = if (maxDiDj > scoreDiDj) {
                maxDiDj
              } else {
                scoreDiDj
              }
            }
          }
          val mmrScoreTemp = lambda * sim1Score - (1 - lambda) * maxDiDj
          if (mmrScore < mmrScoreTemp) {
            mmrScore = mmrScoreTemp
            selectOne = chanelId
          }
        }
        resTopKMap += selectOne -> mmrScore
        stateChannelScore -= selectOne
      }
      val res1 = resTopKMap.toSeq.sortBy(_._2).reverse.map(_._1)
      val res2 = stateChannelScore.toSeq.sortBy(_._2).reverse.map(_._1)
      (res1 ++ res2)
    }
  }
}
