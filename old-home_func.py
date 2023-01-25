if __name__ == "__main__":

    current_energy = START_ENERGY
    consumption_rate = START_CONSUMPTION_RATE
    production_rate = START_PRODUCTION_RATE
    START_CONSUMPTION_RATE = 8
    HOME_ID = os.getpid()
    awaiting_donation = False
    await_donation_counter = AWAIT_DONATION_TIME
    timestamp = 0

    # The unit of time is the second, which is like an hour in simulation
    while True:
        print("~~", timestamp, "~~")
        current_energy -= consumption_rate
        current_energy += production_rate

        surplus = current_energy - MAX_ENERGY
        if surplus > 0:
            if TRADE_POLICY == "GIVE_ONLY":
                # Check the Mq for transaction requests from needy homes
                try:
                    needy_home_id = msg_queue.receive(type=1, block=False)[0].decode()
                    msg_queue.send(str(surplus).encode(), type=int(needy_home_id))
                    surplus = 0
                    current_energy = MAX_ENERGY
                    print(HOME_ID, "gave energy to home", needy_home_id)
                except BusyError:
                    print("No needy home found")
            elif TRADE_POLICY == "SELL_ONLY":
                pass # wait for reaching the threshold of MIN_MARKET_SELL and then sell all surplus
            else: # SELL_IF_NONE
                pass # check in mq for 'in need' request. If none, sell immediately
        
        elif current_energy < LOW_ENERGY_LEVEL:
            # Ask other homes for giveaway, wait for a reply, and if none, buy from market
            if not awaiting_donation: # Let every home know that this home needs energy
                print(HOME_ID, "sent energy request")
                msg_queue.send(str(HOME_ID).encode(), type=1)
                awaiting_donation = True
            else:
                try:
                    energy_received = msg_queue.receive(type=HOME_ID, block=False)
                    awaiting_donation = False
                    current_energy += energy_received
                except BusyError: # No home responded to the request
                    await_donation_counter -= 1
                    if await_donation_counter == 0: # Await time elapsed, buy on market
                        # BUY FROM MARKET
                        print("Buy from market")
                        await_donation_counter = AWAIT_DONATION_TIME
                    pass

        print(f"Energy remaining: {current_energy:.2f}")
        sleep(1)
        timestamp += 1
    # close mq on exit !!!