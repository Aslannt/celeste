package com.aslannt.celeste.data

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

object WakeOnLan {
    fun send(macAddress: String, broadcastAddress: String, port: Int) {
        val mac = macAddress.replace("-", ":").split(":")
        require(mac.size == 6) { "La MAC debe tener 6 pares hexadecimales." }
        val macBytes = mac.map { it.toInt(16).toByte() }.toByteArray()

        val packetBytes = ByteArray(6 + 16 * macBytes.size)
        for (i in 0 until 6) packetBytes[i] = 0xFF.toByte()
        for (i in 6 until packetBytes.size) {
            packetBytes[i] = macBytes[(i - 6) % macBytes.size]
        }

        val address = InetAddress.getByName(broadcastAddress)
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.send(DatagramPacket(packetBytes, packetBytes.size, address, port))
        }
    }
}
