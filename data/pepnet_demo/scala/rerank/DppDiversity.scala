package fm.qingting.RecSysRankService.controllers
import breeze.linalg._
import com.github.plokhotnyuk.jsoniter_scala.core.{JsonValueCodec, readFromString}
import com.github.plokhotnyuk.jsoniter_scala.macros.JsonCodecMaker
import com.redis.RedisClientPool
import fm.qingting.RecSysNg.config.AppConfig.appConf
import fm.qingting.RecSysRankService.controllers.channelUpdateRateReSort.{getChannelFeedback, reChannelScoreSort, reChannelSort}
import fm.qingting.RecSysRankService.log.Logging
import org.apache.hadoop.hbase.HBaseConfiguration
import org.apache.hadoop.hbase.client.{Connection, ConnectionFactory}
import org.json4s.DefaultFormats
import org.json4s.jackson.JsonMethods.parseOpt
import play.api.libs.json._

import scala.Array._
import scala.collection.mutable.{ArrayBuffer, Map => mutableMap}
import scala.util.control._

object DppDiversity extends Logging{
  //dpp算法总入口
  def makeDppReRank(pool: RedisClientPool, chanelScoreMapRaw: Map[String, Float]): Seq[JsObject]= {
    try {
      val (channelScoreTop50Temp, channelScoreBackTemp) = chanelScoreMapRaw.toList.sortBy(_._2).reverse.splitAt(50)
      val channelScoreTop50Map = channelScoreTop50Temp.toMap.map(item => item._1.toInt -> item._2)
      val channelScoreBackList = channelScoreBackTemp.map(item => (item._1.toInt,item._2))
      //根据channel获取cf
      //      val channelCfMap = getCFMap(pool, channelScoreTop50Map.toList.map(item => item._1))
      //调用dpp
      //      val kernelMatrix = buildKernelMatrixCF(channelScoreTop50Map, channelCfMap)
      //根据channel获取word2Vec
      val channelWord2VecMap = getWord2VecEmbeddingMap(pool, channelScoreTop50Map.toList.map(item => item._1))
      //调用dpp
      val kernelMatrix = buildKernelMatrixEmbedding(channelScoreTop50Map, channelWord2VecMap, 16)
      val resTopK = dpp(kernelMatrix, 20, 0.0f)
      //对剩下进行排序
      val resDur2050 = channelScoreTop50Map.--(resTopK.keys.toSeq)
      val resDur2050List = resDur2050.toList.sortBy(_._2).reverse
      val resTopKList = resTopK.toList.sortBy(_._2).reverse
      val resTopKListRawScore=resTopKList.map{item=>(item._1,channelScoreTop50Map.getOrElse(item._1,0.0f))}
      (resTopKListRawScore ++ resDur2050List ++ channelScoreBackList).map(item=>Json.obj("c"->item._1,"s"->item._2))
    }
    catch {
      case NonFatal(_) => chanelScoreMapRaw.toList.sortBy(_._2).reverse.map(item=>Json.obj("c"->item._1,"s"->item._2))
    }
  }
  //乘以专辑rate的dpp打分
  def makeDppReRankWithRate(deviceId:String,hbaseConn: Connection,pool: RedisClientPool, dppPool: RedisClientPool, feedbackPool: RedisClientPool, abtestPool: RedisClientPool, channelScorePool: RedisClientPool, chanelScoreMapRaw: Map[String, Float]): Seq[JsObject]= {
    try {
      val channelScoreFeedback = getChannelFeedback(deviceId, pool, feedbackPool, chanelScoreMapRaw.keySet.toList, "deepfm_1001_")
      val chanelScoreFilterFeedBack = chanelScoreMapRaw.--(channelScoreFeedback.map(item => item.toString))
      val (channelScoreTop50Temp, channelScoreBackTemp) = chanelScoreFilterFeedBack.toList.sortBy(_._2).reverse.splitAt(50)
      val channelScoreTop50Map = channelScoreTop50Temp.toMap.map(item => item._1.toInt -> item._2)
      val (channelScore50100Map, channelScoreBackMap) = channelScoreBackTemp.splitAt(50)
      val channelScore50100List = channelScore50100Map.map(item => item._1.toInt)
      val channelScoreBackList = channelScoreBackMap.map(item => item._1.toInt)
      //根据channel获取cf
      //      val channelCfMap = getCFMap(pool, channelScoreTop50Map.toList.map(item => item._1))
      //调用dpp
      //      val kernelMatrix = buildKernelMatrixCF(channelScoreTop50Map, channelCfMap)
      //根据channel获取word2Vec
      val channelWord2VecMap = getWord2VecEmbeddingMap(dppPool, channelScoreTop50Map.toList.map(item => item._1))
      //调用dpp
      val kernelMatrix = buildKernelMatrixEmbedding(channelScoreTop50Map, channelWord2VecMap, 16)
      val resTopK = dpp(kernelMatrix, 20, 0.0f)
      //对剩下进行排序
      val resDur2050 = channelScoreTop50Map.--(resTopK.keys.toSeq)
      val resDur2050List = resDur2050.toList.sortBy(_._2).reverse.map(item => item._1.toInt)
      val resTopKList = resTopK.toList.sortBy(_._2).reverse.map(item => item._1.toInt)//经过dpp获取的前20个专辑序列
//      val dppRes=resTopKList++resDur2050List++channelScore50100List++channelScoreFeedback++channelScoreBackList
      val dppRes=resTopKList++resDur2050List++channelScore50100List++channelScoreBackList
//      val dppFeedbackFilterRes=resTopKList++resDur2050List++channelScore50100List++channelScoreBackList
//      val dppFeedbackBackRes=resTopKList++resDur2050List++channelScore50100List++channelScoreBackList++channelScoreFeedback

      val dppWithRate = reChannelSort(deviceId, dppRes, hbaseConn)

      val abTest = abtestPool.withClient { client => client.get("novel_quality_rerank:" + deviceId).getOrElse("base")}
//      val saWeightOne = scala.util.Properties.envOrElse("saWeightOne", "S:1.2,A:1.1,B:1.0,C:0.1,D:0.1")
//      val saWeightTwo = scala.util.Properties.envOrElse("saWeightTwo", "S:1.5,A:1.2,B:1.0,C:0.1,D:0.1")

      val rawRes = chanelScoreFilterFeedBack.toSeq.sortBy(_._2).reverse.map(_._1.toInt)
//      val rawFeedbackRes = chanelScoreFilterFeedBack.toSeq.sortBy(_._2).reverse.map(_._1.toInt)
      val dppWithChannelScore = abTest match {
//        case "b" => reChannelScoreSort(rawRes, chanelScoreMapRaw, saWeightOne, channelScorePool)
//        case "c" => reChannelScoreSort(rawRes, chanelScoreMapRaw, saWeightTwo, channelScorePool)
        case "b" => rawRes
        case "c" => dppRes
        case "d" => dppWithRate
//        case "f" => rawFeedbackRes
        case _ => dppWithRate
      }

      if(deviceId=="aebd085fe13960c7cb11d7e01bd6bc63"){
        log.info(s"channel feedback of author : ${channelScoreFeedback.mkString(",")}")
        log.info(s"channel refine rank of author : ${rawRes.mkString(",")}")
        log.info(s"channel dpp rank of author : ${dppRes.mkString(",")}")
        log.info(s"dppWithRate rank of author : ${dppWithRate.mkString(",")}")
        log.info(s"dppWithChannelScore of author : ${dppWithChannelScore.mkString(",")}")
      }

      val resLength = dppWithChannelScore.length
      val resSeq = abTest match {
        case "b" | "c" | "d"  =>  dppWithChannelScore.zipWithIndex.map(item => (item._1, (resLength - item._2) / resLength.toFloat ))
        case _ => dppWithChannelScore.map(item=>(item, chanelScoreMapRaw.getOrElse(item.toString,0.0f)))
      }

      resSeq.map(item => Json.obj("c" -> item._1, "s" -> item._2))

    }
    catch {
      case NonFatal(_) => chanelScoreMapRaw.toList.sortBy(_._2).reverse.map(item=>Json.obj("c"->item._1,"s"->item._2))
    }
  }

  //创建核矩阵，根据deepFm分数和专辑之间的协同过滤打分
  def buildKernelMatrixCF(channelScore: Map[Int, Float], channelCf: Map[Int, Map[Int, Float]]): Map[String, Any] = {
    val (channelIdArr, channelScoreArr) = channelScore.toArray.unzip
    val rankScoreArrBuf: ArrayBuffer[Float] = ArrayBuffer()
    for (i <- 0 until channelScoreArr.size) {
      rankScoreArrBuf ++= channelScoreArr
    }
    val rankScoreMatrixLeft = new DenseMatrix[Float](channelScore.size, channelScore.size, rankScoreArrBuf.toArray)
    val rankScoreMatrixRight = rankScoreMatrixLeft.t
    val cfScoreArr: ArrayBuffer[Float] = ArrayBuffer()
    var maxValue = Float.MinValue
    channelIdArr.foreach(channelI =>
      channelIdArr.foreach(channelJ =>
        if (channelI == channelJ) {
          cfScoreArr.append(-1.0f)
        } else {
          if (channelCf.contains(channelI) && channelCf(channelI).contains(channelJ)) {
            cfScoreArr.append(channelCf(channelI)(channelJ))
            maxValue = if (channelCf(channelI)(channelJ) > maxValue) {
              channelCf(channelI)(channelJ)
            } else {
              maxValue
            }
          } else {
            cfScoreArr.append(0.0f)
          }
        }
      ))
    val cfScoreArrNormal = cfScoreArr.toArray.map { item =>
      item match {
        case item if item >= 0.0f => item / maxValue
        case item if item < 0.0f => 1.0f
      }
    }
    val simMatrix = new DenseMatrix[Float](channelIdArr.length, channelIdArr.length, cfScoreArrNormal)
    val kernelMatrix = rankScoreMatrixLeft.*:*(simMatrix).*:*(rankScoreMatrixRight)

    Map("kernelMatrix" -> kernelMatrix.asInstanceOf[Any], "channelIdArr" -> channelIdArr.asInstanceOf[Any])

  }

  //创建核矩阵，根据deepFm分数和专辑embedding
  def buildKernelMatrixEmbedding(channelScore: Map[Int, Float], channelEmbedding: Map[Int, Array[Float]], embeddingSize: Int): Map[String, Any] = {
    val (channelIdArr, channelScoreArr) = channelScore.toArray.unzip
    val rankScoreArrBuf: ArrayBuffer[Float] = ArrayBuffer()
    for (i <- 0 until channelScoreArr.size) {
      rankScoreArrBuf ++= channelScoreArr
    }
    val rankScoreMatrixLeft = new DenseMatrix[Float](channelScore.size, channelScore.size, rankScoreArrBuf.toArray)

    val rankScoreMatrixRight = rankScoreMatrixLeft.t

    val itemEmbeddingArrBuf: ArrayBuffer[Array[Float]] = ArrayBuffer()
    channelIdArr.foreach { channelId =>
      itemEmbeddingArrBuf.append(channelEmbedding.getOrElse(channelId, new Array[Float](embeddingSize)))
    }
    val itemEmbeddingArr = itemEmbeddingArrBuf.toArray.flatten
    val itemEmbeddingMatrixT = new DenseMatrix[Float](embeddingSize, channelIdArr.size, itemEmbeddingArr)
    val itemEmbeddingMatrix = itemEmbeddingMatrixT.t
    val simMatrix = itemEmbeddingMatrix.*(itemEmbeddingMatrixT)
    val kernelMatrix = rankScoreMatrixLeft.*:*(simMatrix).*:*(rankScoreMatrixRight)
    Map("kernelMatrix" -> kernelMatrix.asInstanceOf[Any], "channelIdArr" -> channelIdArr.asInstanceOf[Any])

  }
  //dpp求解过程
  //具体参考实现过程 https://zhuanlan.zhihu.com/p/94464178，https://zhuanlan.zhihu.com/p/95607668
  def dpp(kernelMatrixAndChannelIdArr: Map[String, Any], maxIter: Int, epsilon: Float): Map[Int, Float] = {
    val channelIdArr = kernelMatrixAndChannelIdArr.getOrElse("channelIdArr", null).asInstanceOf[Array[Int]]
    val Z = range(0, channelIdArr.size)
    val kernelMatrix = kernelMatrixAndChannelIdArr.getOrElse("kernelMatrix", null).asInstanceOf[DenseMatrix[Float]]
    val itemCount = channelIdArr.size //所有专辑的数量
    val c = DenseMatrix.zeros[Float](maxIter, itemCount)
    val d = diag(kernelMatrix)
    var j = argmax(d)
    val Y: ArrayBuffer[Int] = ArrayBuffer()
    Y.append(j)
    var Yg: mutableMap[Int, Float] = mutableMap()
    Yg += (channelIdArr(j) -> d(j))
    var iter = 0
    val loop = new Breaks
    loop.breakable {
      while (iter < maxIter) {
        val ZY = Z.toSet.--(Y.toSet)
        ZY.foreach { channelIndex =>
          var ei = 0.0f
          if (iter == 0) {
            ei = kernelMatrix(j, channelIndex) / (math.sqrt(d(j).toDouble + 0.0000001).toFloat)
          } else {
            val cj = c(0 until (iter), j)
            val ci = c(0 until (iter), channelIndex)
            val cijDot = cj.dot(ci)
            ei = (kernelMatrix(j, channelIndex) - cijDot) / (math.sqrt(d(j).toDouble + 0.0000001).toFloat)
          }
          c(iter, channelIndex) = ei
          d(channelIndex) = d(channelIndex) - ei * ei
        }
        d(j) = 0.0f
        j = argmax(d)
        if (d(j) < epsilon) {
          loop.break
        }
        Y.append(j)
        Yg += (channelIdArr(j) -> d(j))
        iter += 1
      }
    }
    Yg.toMap
  }

  //创建获取CF打分时用到的redis-pool
  def createRedisPool(database: Int): RedisClientPool = {
    val host = appConf.getString("online_redis.host")
    val port = appConf.getInt("online_redis.port")
    val auth = appConf.getString("online_redis.auth")
    new RedisClientPool(
      host = host,
      port = port,
      database = database,
      secret = Some(auth),
      timeout = 3600
    )
  }

  //创建获取feedback打分时用到的redis-pool
  def createFeedbackRedisPool(database: Int): RedisClientPool = {
    val host = appConf.getString("online_feedback_redis.host")
    val port = appConf.getInt("online_feedback_redis.port")
    val auth = appConf.getString("online_feedback_redis.auth")
    new RedisClientPool(
      host = host,
      port = port,
      database = database,
      secret = Some(auth),
      timeout = 3600
    )
  }

  //创建获取feedback打分时用到的redis-pool
  def createABTestPool(database: Int): RedisClientPool = {
    val host = appConf.getString("ab_redis.host")
    val port = appConf.getInt("ab_redis.port")
    val auth = appConf.getString("ab_redis.auth")
    new RedisClientPool(
      host = host,
      port = port,
      database = database,
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
  def getCFMap(pool: RedisClientPool, channelIds: Seq[Int]): Map[Int, Map[Int, Float]] = {
    pool.withClient { client =>
      val cfStrMap = client
        .hmget[Int, String]("allChannels:cf", channelIds: _*)
        .getOrElse(Map.empty)
        .filter(_._2.nonEmpty)
      cfStrMap.map {
        case (channelId, str) =>
          val data = str.split(",").map { s =>
            val a = s.split("_")
            a.head.toInt -> a.last.toFloat
          }
          channelId -> data.toMap
      }
    }
  }

  //获取专辑的Dssm-embedding(200维)
  def getDssmEmbeddingMap(pool: RedisClientPool, channelIdsRaw: Seq[Int]): Map[Int, Array[Double]] = {
    implicit val ChannelFeatureRedisCodec: JsonValueCodec[Array[Double]] = JsonCodecMaker.make
    val channelIds = channelIdsRaw.map(item => "dssm_hard_1002_" + item.toString)
    pool.withClient { client =>
      val channelFeatures = client
        .mget[String](channelIds.head, channelIds.tail: _*).getOrElse(List.empty[Option[String]])
      channelIdsRaw.zip(channelFeatures).map(item => {
        item._2 match {
          case None => item._1 -> new Array[Double](200)
          case _ => item._1 -> readFromString[Array[Double]](item._2.get)
        }
      }).toMap[Int, Array[Double]]
    }
  }

  //获取专辑的word2vec-embedding(16维)
  def getWord2VecEmbeddingMap(pool: RedisClientPool, channelIdsRaw: Seq[Int]): Map[Int, Array[Float]] = {
    implicit val ChannelFeatureRedisCodec: JsonValueCodec[Array[Float]] = JsonCodecMaker.make
    val channelIds = channelIdsRaw.map(item => "channel:embedding:word2vec:" + item.toString)
    pool.withClient { client =>
      val channelFeatures = client
        .mget[String](channelIds.head, channelIds.tail: _*).getOrElse(List.empty[Option[String]])
      channelIdsRaw.zip(channelFeatures).map(item => {
        item._2 match {
          case None => item._1 -> new Array[Float](16)
          case _ => item._1 -> readFromString[Array[Float]](item._2.get)
        }
      }).toMap[Int, Array[Float]]
    }
  }
}
