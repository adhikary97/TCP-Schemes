#!/usr/bin/env python3

import os
import sys
import socket
import json
import argparse


# This function is to handle receiving multiple packets at the same time
def handle_multiple(data):
    end = 0
    start = 0
    packets = list()
    while end < len(data):
        packet, end = json.JSONDecoder().raw_decode(data, start)
        packets.append(packet)
        start = end
    if packets:
        if len(packets) == 0:
            return packets[0]
        return packets


# This function is to write the received packets to a file after receiving all the packets
def write_to_file(received):
    with open(os.path.dirname(os.path.abspath(__file__)) + '/received.txt', 'w') as fil:
        for i in sorted(received.keys()):
            fil.write(received[i])


# Handles sending ACK's
def send_ack(conn, received):
    ACK = {
        'sequence_number': sorted(received)
    }
    conn.sendall(json.dumps(ACK).encode())


# This function is handling all the receiving and replying with ack's based on the scheme
def receive_packets(sock, conn, scheme):
    received = dict()
    recents = list()
    count = 0
    end_flag = 0
    try:
        while True:
            sock.settimeout(.1)
            data = conn.recv(4096)
            if data:
                data = handle_multiple(data.decode())
                if scheme == 0:  # stop and go
                    data = data[0]
                    seq_num = data['sequence_number']
                    ws = data['window_size']
                    received[seq_num] = data['data']
                    # print(data)
                    ACK = {
                        'sequence_number': seq_num
                    }
                    conn.sendall(json.dumps(ACK).encode())
                    if data['end_flag'] and len(received) == seq_num - min(received.keys()) + 1:
                        # print(received)
                        write_to_file(received)
                        sock.close()
                        break
                elif scheme == 1:  # cumulative
                    if data:
                        for loaded in data:
                            seq_num = loaded['sequence_number']
                            ws = loaded['window_size']
                            if seq_num not in recents:
                                recents.append(seq_num)
                            while len(recents) > 2 * ws:
                                recents.pop(0)
                            received[seq_num] = loaded['data']
                            if loaded['end_flag']:
                                end_flag = 1
                        if len(received.keys()) % ws == 0:
                            send_ack(conn, recents)
                        if end_flag and len(received) == max(received.keys()) - min(received.keys()) + 1:
                            send_ack(conn, recents)
                            write_to_file(received)
                            sock.close()
                            break
                elif scheme == 2:  # selective
                    if data:
                        for loaded in data:
                            seq_num = loaded['sequence_number']
                            ws = loaded['window_size']
                            if seq_num not in recents:
                                recents.append(seq_num)
                            while len(recents) > 2 * ws:
                                recents.pop(0)
                            received[seq_num] = loaded['data']
                            if loaded['end_flag']:
                                end_flag = 1
                        send_ack(conn, recents)
                        if end_flag and len(received) == max(received.keys()) - min(received.keys()) + 1:
                            send_ack(conn, recents)
                            write_to_file(received)
                            sock.close()
                            break
                count += 1
    except KeyboardInterrupt:
        write_to_file(received)
        sock.close()
    except BrokenPipeError:
        write_to_file(received)
        sock.close()


def main(argv):
    IP = argv.IP
    PORT = argv.PORT
    scheme = argv.scheme
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((IP, PORT))
    sock.listen()
    conn, addr = sock.accept()
    with conn:
        print('Connected by', addr)
        receive_packets(sock, conn, scheme)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='''These are the arguments required.''')
    parser.add_argument('IP', type=str, default='127.0.0.1',
                        help='Receiver IP, i.e. 127.0.0.1')
    parser.add_argument('PORT', type=int, default=5000,
                        help='Receiver Port, i.e. 5000')
    parser.add_argument('scheme', type=int, default=0,
                        help='TCP Scheme, i.e. 0=stop-and-go,1=cumulative,2=selective')
    args = parser.parse_args()
    main(args)
