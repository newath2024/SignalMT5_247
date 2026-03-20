from scanner import main_loop, parse_args


if __name__ == "__main__":
    args = parse_args()
    main_loop(run_once=args.once, poll_interval_sec=args.interval)
