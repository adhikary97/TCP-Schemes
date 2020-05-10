#!/usr/bin/env python3

import sys
import socket
from socket import timeout
import json
import asyncio
from random import randint
import time
import argparse
from receiver import handle_multiple

time_outs = dict()
acknowledged = list()
packets_to_send = dict()


# This function handles sending all the packets to the receiver based on the scheme
async def send_packets(sock, file_name, scheme):
    sequence_number = randint(1000, 9999)
    order = 0
    with open(file_name, 'r') as fil:
        data = fil.read(1024)
        while data:
            packets_to_send[sequence_number] = {
                'sequence_number': sequence_number,
                'data': data,
                'window_size': 3,
                'order': order,
                'end_flag': 0,
                'scheme': scheme
            }
            sequence_number += 1
            order += 1
            data = fil.read(1024)
    packets_to_send[sequence_number-1]['end_flag'] = 1
    count = 0
    if scheme == 0:  # stop and go
        while True:
            if count == 0:
                num = list(packets_to_send.keys())[0]
                sock.send(json.dumps(packets_to_send[num]).encode())
                time_outs[num] = time.time()
                count += 1
                num += 1
            elif num - 1 in acknowledged:
                if num in packets_to_send:
                    sock.send(json.dumps(packets_to_send[num]).encode())
                    time_outs[num] = time.time()
                    num += 1
                else:
                    break
            elif time.time() - time_outs[num-1] > 1:
                if num - 1 in packets_to_send:
                    sock.send(json.dumps(packets_to_send[num-1]).encode())
                    time_outs[num] = time.time()
                else:
                    break
            await asyncio.sleep(.1)
    elif scheme == 1:  # cumulative ack
        num = list(packets_to_send.keys())[0]
        ws = packets_to_send[num]['window_size']
        while True:
            if count == 0:
                for i in range(ws):
                    if num + i in packets_to_send:
                        sock.send(json.dumps(packets_to_send[num + i]).encode())
                        time_outs[num + i] = time.time()
                    else:
                        break
                count += 1
            else:
                flag = 1
                for i in time_outs:
                    if time.time() - time_outs[i] > .1 and time_outs[i] != -1:
                        print('resend', i, packets_to_send[i])
                        sock.send(json.dumps(packets_to_send[i]).encode())
                        time_outs[i] = time.time()
                        flag = 0
                if flag:
                    num += ws
                    time_outs.clear()
                    for i in range(ws):
                        if num + i in packets_to_send:
                            sock.send(json.dumps(packets_to_send[num + i]).encode())
                            time_outs[num + i] = time.time()
                        else:
                            break
            if len(acknowledged) == len(packets_to_send) and len(packets_to_send) != 0:
                break
            await asyncio.sleep(.1)
    elif scheme == 2:  # selective ack
        num = list(packets_to_send.keys())[0]
        ws = packets_to_send[num]['window_size']
        while True:
            if count == 0:
                for i in range(ws):
                    if num + i in packets_to_send:
                        sock.send(json.dumps(packets_to_send[num+i]).encode())
                        time_outs[num+i] = time.time()
                    else:
                        break
                count += 1
            else:
                temp = list(time_outs.keys()).copy()
                for i in temp:
                    if time.time() - time_outs[i] > .1 and time_outs[i] != -1:
                        print('resend', i, packets_to_send[i])
                        sock.send(json.dumps(packets_to_send[i]).encode())
                        time_outs[i] = time.time()
                    elif time_outs[i] == -1:
                        time_outs.pop(i)
                        num = max(acknowledged) + 1
                for i in range(ws - len(time_outs)):
                    if num + i in packets_to_send:
                        sock.send(json.dumps(packets_to_send[num + i]).encode())
                        time_outs[num + i] = time.time()
                    else:
                        break
            if len(acknowledged) == len(packets_to_send) and len(packets_to_send) != 0:
                break
            await asyncio.sleep(.1)


# This function handles receiving the ack's from the receiver
async def receive_acks(sock, scheme):
    while True:
        try:
            sock.settimeout(.2)
            data, addr = sock.recvfrom(4096)
            if data:
                if scheme == 0:  # stop and go receive
                    data = handle_multiple(data.decode())
                    data = data[0]
                    if data['sequence_number'] not in acknowledged and data['sequence_number'] in time_outs:
                        acknowledged.append(data['sequence_number'])
                        time_outs[data['sequence_number']] = -1
                        print(data['sequence_number'], 'acknowledged')
                elif scheme == 1 or scheme == 2:  # cumulative and selective receive
                    data = handle_multiple(data.decode())
                    if data:
                        for packet in data:
                            for i in packet['sequence_number']:
                                if i not in acknowledged:
                                    acknowledged.append(i)
                                    time_outs[i] = -1
                                    print(i, 'acknowledged')
            if len(acknowledged) == len(packets_to_send) and len(packets_to_send) != 0:
                break
        except timeout:
            await asyncio.sleep(.1)
        except KeyboardInterrupt:
            break


def main(argv):
    receiver_ip = argv.r_ip  # The receiver's IP address
    receiver_port = argv.r_port  # The port used by the receiver
    sender_ip = argv.s_ip
    sender_port = argv.s_port
    file_name = argv.file
    scheme = argv.scheme
    print(receiver_ip, receiver_port, sender_ip, sender_port, file_name)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((sender_ip, sender_port))
    sock.connect((receiver_ip, receiver_port))

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.gather(
            send_packets(sock, file_name, scheme),
            receive_acks(sock, scheme)
        ))
    except KeyboardInterrupt:
        print('shutting down.')
    except BrokenPipeError:
        print('shutting down.')
    finally:
        print('done sending.')
        sock.close()
        loop.stop()
        loop.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='''These are the arguments required.''')
    parser.add_argument('r_ip', type=str, default='127.0.0.1', help='Receiver IP, i.e. 127.0.0.1')
    parser.add_argument('r_port', type=int, default=5000, help='Receiver Port, i.e. 5000')
    parser.add_argument('s_ip', type=str, default='127.0.0.1', help='Sender IP, i.e. 127.0.0.1')
    parser.add_argument('s_port', type=int, default=3000, help='Sender Port, i.e. 3000')
    parser.add_argument('file', type=str, default='message.txt', help='Filename, i.e. message.txt')
    parser.add_argument('scheme', type=int, default=0, help='TCP Scheme, i.e. 0=stop-and-go,1=cumulative,2=selective')
    args = parser.parse_args()
    main(args)
