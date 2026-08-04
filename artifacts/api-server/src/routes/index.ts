import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import playerRouter from "./player";
import charactersRouter from "./characters";
import shopRouter from "./shop";
import inventoryRouter from "./inventory";
import dailyRouter from "./daily";
import missionsRouter from "./missions";
import leaderboardsRouter from "./leaderboards";
import casinoRouter from "./casino";
import marketplaceRouter from "./marketplace";
import notificationsRouter from "./notifications";
import transactionsRouter from "./transactions";
import announcementsRouter from "./announcements";
import adminRouter from "./admin";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(playerRouter);
router.use(charactersRouter);
router.use(shopRouter);
router.use(inventoryRouter);
router.use(dailyRouter);
router.use(missionsRouter);
router.use(leaderboardsRouter);
router.use(casinoRouter);
router.use(marketplaceRouter);
router.use(notificationsRouter);
router.use(transactionsRouter);
router.use(announcementsRouter);
router.use(adminRouter);

export default router;
